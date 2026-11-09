"""Signed operations events. Attendance uses server UTC; money uses minor units."""
import hashlib
import json
import secrets
import uuid
from calendar import monthrange
from contextlib import closing,nullcontext
from datetime import datetime,date,time,timedelta,timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from backend.erp.service import ERPError,number,iso
from backend.erp.audit import verify_ledger
from backend.workspace.pos import catalog,quote,recipe
from backend.integrity import canonical,sign,verify,IntegrityError

UTC=timezone.utc
MANAGERS={'owner','manager'}

def instant(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError()
        return d.astimezone(UTC)
    except (ValueError,TypeError,AttributeError):raise ERPError('Timestamp must include timezone')

def identifier(value):
    if not isinstance(value,str) or not value.strip() or len(value)>120:raise ERPError('Identifier required, maximum 120 characters')
    return value

def period(value):
    if not isinstance(value,str) or len(value)!=7:raise ERPError('Month must be YYYY-MM')
    iso(value+'-01');return value

class Workspace:
    def __init__(self,erp,clock=None):
        self.erp=erp;self.key=erp.audit_key;self.clock=clock or (lambda:datetime.now(UTC))
        with closing(erp.connect()) as c:c.executescript(Path(__file__).with_name('schema.sql').read_text())
    def now(self):return self.clock().astimezone(UTC).replace(microsecond=0)
    def access(self,identity,branch,manager=False):
        if branch not in identity.get('branches',[]):raise PermissionError('No permission for this branch')
        if identity.get('role') not in (MANAGERS if manager else {'owner','manager','cashier'}):raise PermissionError('Role not allowed')
        identifier(identity.get('user_id') or identity.get('name'))
        with closing(self.erp.connect()) as c:
            if not c.execute('SELECT 1 FROM erp_branches WHERE id=?',(branch,)).fetchone():raise ERPError('Unknown branch')
    def state(self,c):
        verify_ledger(c,self.key)
        previous=c.execute('SELECT signature FROM erp_integrity_genesis WHERE id=1').fetchone()[0]
        state={'employees':{},'shifts':{},'campaigns':{},'grants':{},'reorders':{},'payrolls':{},'tax':{},'settings':{},'sales':[],'menu':{},'receipt_profiles':{},'tables':{},'orders':{},'seq':0}
        for expected,row in enumerate(c.execute('SELECT * FROM workspace_events ORDER BY seq').fetchall(),1):
            record=dict(row);signature=record.pop('signature')
            if record['seq']!=expected or record['previous_signature']!=previous:raise IntegrityError('Workspace audit chain broken')
            verify(self.key,record,signature);previous=signature;state['seq']=expected
            p=json.loads(record['payload']);kind=record['kind']
            if kind=='employee':state['employees'][p['employee_id']]=p
            elif kind=='shift_open':state['shifts'][p['shift_id']]={**p,'ended_at':None,'reviewed':False}
            elif kind=='shift_close':state['shifts'][p['shift_id']].update(p)
            elif kind in ('shift_review','till_open'):state['shifts'][p['shift_id']].update(p)
            elif kind=='campaign':state['campaigns'][p['campaign_id']]=p
            elif kind=='grant':state['grants'][p['grant_id']]={**p,'used':False}
            elif kind=='revoke_grant':state['grants'][p['grant_id']]['revoked']=True
            elif kind=='receipt_profile':state['receipt_profiles'][record['branch_id']]=p
            elif kind=='menu':state['menu'][(record['branch_id'],p['id'])]=p
            elif kind=='table':state['tables'][(record['branch_id'],p['id'])]=p
            elif kind=='table_remove':state['tables'].pop((record['branch_id'],p['id']),None)
            elif kind=='order_save':state['orders'][p['order_id']]=p
            elif kind=='sale':
                if p.get('order_id'):state['orders'][p['order_id']]['paid']=True
                state['sales'].append(p)
                if p.get('grant_id'):state['grants'][p['grant_id']]['used']=True
            elif kind=='reorder':state['reorders'][(record['branch_id'],p['item_id'])]=p
            elif kind=='payroll':state['payrolls'][(record['branch_id'],p['month'])]=p
            elif kind=='tax':state['tax'][record['branch_id']]=p
            elif kind=='settings':state['settings'][record['branch_id']]=p
            else:raise IntegrityError('Unknown signed workspace event')
        return state
    def emit(self,c,identity,branch,kind,payload,request_key,request_hash=None):
        previous=c.execute('SELECT seq,signature FROM workspace_events ORDER BY seq DESC LIMIT 1').fetchone()
        row={'seq':previous[0]+1 if previous else 1,'event_id':uuid.uuid4().hex,'request_key':request_key,
            'request_hash':request_hash or hashlib.sha256(canonical(payload).encode()).hexdigest(),
            'actor_id':identity.get('user_id') or identity['name'],'role':identity['role'],'branch_id':branch,'kind':kind,
            'at':self.now().isoformat(),'payload':canonical(payload),
            'previous_signature':previous[1] if previous else c.execute('SELECT signature FROM erp_integrity_genesis WHERE id=1').fetchone()[0]}
        c.execute('INSERT INTO workspace_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(*row.values(),sign(self.key,row)))
        return payload
    def action(self,identity,branch,kind,payload,key):
        if not isinstance(kind,str):raise ERPError('Action kind must be text')
        self.access(identity,branch,manager=kind not in ('shift_open','shift_close','till_open','order_save'))
        if not isinstance(payload,dict):raise ERPError('Object payload required')
        identifier(key);digest=hashlib.sha256(canonical({'kind':kind,'branch':branch,'payload':payload,'actor':identity.get('user_id') or identity['name']}).encode()).hexdigest()
        with closing(self.erp.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE');state=self.state(c)
            old=c.execute('SELECT request_hash,payload FROM workspace_events WHERE request_key=?',(key,)).fetchone()
            if old:
                if old[0]!=digest:raise ERPError('Request key already used for a different action')
                previous=json.loads(old[1])
                if kind=='grant':return {k:v for k,v in previous.items() if k!='key_hash'}|{'status':'already_issued','activation_key':None}
                return previous
            now=self.now();p=dict(payload)
            required={
                'employee':({'employee_id','name','hourly_minor','inactive_from'}, {'employee_id','name','hourly_minor'}),
                'settings':({'timezone'}, {'timezone'}),
                'receipt_profile':({'merchant_name','address','vat_number'},{'merchant_name','address','vat_number'}),
                'menu':({'id','name','names','price_minor','vat_bps','category','icon','active','recipe','components'},{'id','name','names','price_minor','vat_bps','category','icon','active','recipe','components'}),
                'table':({'id','label','seats','x','y'},{'id','label','seats','x','y'}),
                'table_remove':({'id'},{'id'}),
                'order_save':({'table_id','items','revision'},{'table_id','items','revision'}),
                'shift_open':({'opening_cash_minor'},set()),
                'shift_close':({'shift_id','break_seconds','counted_cash_minor','handover_to','note'}, {'shift_id','counted_cash_minor'}),
                'till_open':({'shift_id','opening_cash_minor'},{'shift_id','opening_cash_minor'}),
                'revoke_grant':({'grant_id','reason'},{'grant_id','reason'}),
                'shift_review':({'shift_id','reason','start','end','break_seconds'},{'shift_id','reason'}),
                'campaign':({'campaign_id','name','discount_bps','enabled','starts_at','ends_at'}, {'campaign_id','name','discount_bps','enabled','starts_at','ends_at'}),
                'grant':({'campaign_id','employee_id','ttl_minutes'}, {'campaign_id','employee_id'}),
                'reorder':({'item_id','minimum','daily_target','weekly_target'}, {'item_id','minimum','daily_target','weekly_target'}),
                'tax':({'rate_bps'}, {'rate_bps'})}
            if kind not in required:raise ERPError('Unsupported workspace action')
            allowed,needed=required[kind]
            if set(p)-allowed or needed-set(p):raise ERPError('Invalid fields for workspace action')
            if kind=='receipt_profile':
                identifier(p['merchant_name'])
                if not isinstance(p['address'],str) or not 1<=len(p['address'])<=500 or not isinstance(p['vat_number'],str) or len(p['vat_number'])>120:raise ERPError('Invalid receipt business details')
            elif kind=='menu':
                identifier(p['id']);identifier(p['name']);number(p['price_minor'],1,100000000);number(p['vat_bps'],0,10000)
                if type(p['active']) is not bool or p['category'] not in ('main','drink','dessert','combo','entree','plat','vin','supplementaire') or p['icon'] not in ('rice','chicken','salad','drink','cake','combo'):raise ERPError('Invalid menu settings')
                if not isinstance(p['names'],dict) or set(p['names'])!={'vi','en','fr','de'}:raise ERPError('Provide menu names in all four languages')
                for name in p['names'].values():identifier(name)
                if not isinstance(p['recipe'],list) or not isinstance(p['components'],list) or len(p['recipe'])>30 or len(p['components'])>20:raise ERPError('Invalid recipe or combo')
                if p['components'] and p['recipe']:raise ERPError('Combo recipe is derived from components')
                menu=catalog(c,state,branch)
                for x in p['recipe']:
                    if not isinstance(x,dict) or set(x)!={'item_id','quantity'} or not isinstance(x['item_id'],str) or not c.execute('SELECT 1 FROM erp_items WHERE id=?',(x['item_id'],)).fetchone():raise ERPError('Unknown recipe ingredient')
                    number(x['quantity'],1,100000000)
                for x in p['components']:
                    if not isinstance(x,dict) or set(x)!={'product_id','quantity'} or not isinstance(x['product_id'],str) or x['product_id']==p['id'] or x['product_id'] not in menu or menu[x['product_id']].get('components'):raise ERPError('Invalid combo component')
                    number(x['quantity'],1,100)
                p['branch_id']=branch
            elif kind=='table':
                identifier(p['id']);identifier(p['label']);number(p['seats'],1,100)
                for field in ('x','y'):number(p[field],0,90)
            elif kind=='table_remove':
                identifier(p['id'])
                if (branch,p['id']) not in state['tables']:raise ERPError('Unknown table')
                if any(o['branch_id']==branch and o['table_id']==p['id'] and not o.get('paid') for o in state['orders'].values()):
                    raise ERPError('Cannot remove a table with an open order')
            elif kind=='order_save':
                identifier(p['table_id'])
                table=state['tables'].get((branch,p['table_id']))
                if not table:raise ERPError('Unknown table')
                current=next((o for o in state['orders'].values() if o['branch_id']==branch and o['table_id']==p['table_id'] and not o.get('paid')),None)
                if number(p['revision'],0)!=(current['revision'] if current else 0):raise ERPError('Table order changed; refresh before saving')
                quote(catalog(c,state,branch),p['items'])
                p.update(order_id=current['order_id'] if current else uuid.uuid4().hex,branch_id=branch,revision=p['revision']+1,paid=False,updated_by=identity['user_id'])
            elif kind=='settings':
                try:ZoneInfo(p['timezone'])
                except (ZoneInfoNotFoundError,TypeError,ValueError):raise ERPError('Valid IANA timezone required')
            elif kind=='employee':
                employee=identifier(p['employee_id']);identifier(p['name']);number(p['hourly_minor'],1,100000000)
                old_employee=state['employees'].get(employee)
                if old_employee and old_employee['branch_id']!=branch:raise ERPError('Employee belongs to another branch')
                inactive=p.get('inactive_from')
                if inactive:
                    iso(inactive)
                    local_day=now.astimezone(ZoneInfo(self.zone(state,branch))).date().isoformat()
                    if inactive<local_day:raise ERPError('Staffing changes cannot be backdated')
                p.update(branch_id=branch,inactive_from=inactive or None,updated_at=now.isoformat())
            elif kind=='shift_open':
                employee=self.employee(identity,state,branch)
                existing=next((s for s in state['shifts'].values() if s['employee_id']==employee['employee_id'] and not s['ended_at']),None)
                if existing:
                    if existing['branch_id']!=branch:raise ERPError('Employee already has an active shift at another branch')
                    return existing
                zone=self.zone(state,branch);local_day=now.astimezone(ZoneInfo(zone)).date().isoformat()
                if employee.get('inactive_from') and local_day>=employee['inactive_from']:raise ERPError('Employee is no longer scheduled for new shifts')
                handover=next((s for s in reversed(list(state['shifts'].values())) if s['branch_id']==branch and s.get('handover_to')==employee['employee_id'] and s['ended_at'] and not any(v.get('handover_from')==s['shift_id'] for v in state['shifts'].values())),None)
                p={'shift_id':uuid.uuid4().hex,'employee_id':employee['employee_id'],'employee_name':employee['name'],'branch_id':branch,
                    'started_at':now.isoformat(),'hourly_minor':employee['hourly_minor'],'timezone':zone,
                    'opening_cash_minor':handover['counted_cash_minor'] if handover else number(p.get('opening_cash_minor',0),0),
                    'opening_confirmed':False,'handover_from':handover['shift_id'] if handover else None}
            elif kind=='till_open':
                shift=self.shift_access(identity,state,branch,p['shift_id'])
                if shift['ended_at'] or shift.get('opening_confirmed') or any(s.get('shift_id')==shift['shift_id'] for s in state['sales']):raise ERPError('Opening till can only be confirmed once before sales')
                amount=number(p['opening_cash_minor'],0)
                p={'shift_id':shift['shift_id'],'opening_cash_minor':amount,'opening_confirmed':True,'opening_difference_minor':amount-shift['opening_cash_minor']}
            elif kind=='shift_close':
                shift=self.shift_access(identity,state,branch,p['shift_id'])
                if shift['ended_at']:raise ERPError('Shift already ended')
                start=instant(shift['started_at']);seconds=int((now-start).total_seconds())
                if seconds<0:raise ERPError('Server clock moved backwards')
                pause=number(p.get('break_seconds',0),0,seconds)
                counted=number(p['counted_cash_minor'],0)
                note=p.get('note','');target=p.get('handover_to')
                if not isinstance(note,str) or len(note)>1000:raise ERPError('Handover note too long')
                if target:
                    if target==shift['employee_id'] or target not in state['employees'] or state['employees'][target]['branch_id']!=branch:raise ERPError('Invalid handover recipient')
                expected=self.shift_cash(c,state,shift)
                p={'shift_id':shift['shift_id'],'ended_at':now.isoformat(),'break_seconds':pause,'paid_seconds':seconds-pause,
                    'counted_cash_minor':counted,'expected_cash_minor':expected,'cash_difference_minor':counted-expected,
                    'handover_to':target or None,'note':note,'needs_review':seconds>16*3600,'reviewed':False}
            elif kind=='shift_review':
                shift=self.shift_access(identity,state,branch,p['shift_id'])
                if not shift['ended_at']:raise ERPError('End shift before review')
                identifier(p['reason'])
                if any(pay.get('shift_ids') and shift['shift_id'] in pay['shift_ids'] for pay in state['payrolls'].values()):raise ERPError('Accrued payroll shifts require separate adjusting payroll, not editing')
                start=instant(p.get('start',shift['started_at']));end=instant(p.get('end',shift['ended_at']))
                if end>now or start>end or end-start>timedelta(hours=72):raise ERPError('Reviewed shift times are invalid')
                pause=number(p.get('break_seconds',shift['break_seconds']),0,int((end-start).total_seconds()))
                # Prevent a correction from overlapping another shift for the same employee.
                for other in state['shifts'].values():
                    if other['employee_id']==shift['employee_id'] and other['shift_id']!=shift['shift_id']:
                        other_end=instant(other['ended_at']) if other['ended_at'] else now
                        if start<other_end and end>instant(other['started_at']):raise ERPError('Reviewed shift overlaps another shift')
                p={'shift_id':shift['shift_id'],'started_at':start.isoformat(),'ended_at':end.isoformat(),'break_seconds':pause,
                    'paid_seconds':int((end-start).total_seconds())-pause,'needs_review':False,'reviewed':True,'review_reason':p['reason']}
            elif kind=='campaign':
                identifier(p['campaign_id']);identifier(p['name']);number(p['discount_bps'],1,10000)
                if type(p['enabled']) is not bool:raise ERPError('enabled must be boolean')
                if instant(p['starts_at'])>=instant(p['ends_at']):raise ERPError('Campaign dates are invalid')
                previous=state['campaigns'].get(p['campaign_id'])
                if previous and previous['branch_id']!=branch:raise ERPError('Campaign belongs to another branch')
                p['branch_id']=branch
            elif kind=='grant':
                campaign=state['campaigns'].get(p['campaign_id'])
                if not campaign or campaign['branch_id']!=branch or not campaign['enabled'] or not instant(campaign['starts_at'])<=now<instant(campaign['ends_at']):raise ERPError('Campaign is not active')
                employee=state['employees'].get(p['employee_id'])
                if not employee or employee['branch_id']!=branch:raise ERPError('Invalid cashier for this branch')
                raw=secrets.token_urlsafe(24);grant={'grant_id':uuid.uuid4().hex,'campaign_id':campaign['campaign_id'],'employee_id':employee['employee_id'],
                    'branch_id':branch,'key_hash':sign(self.key,raw),'expires_at':min(now+timedelta(minutes=number(p.get('ttl_minutes',15),1,60)),instant(campaign['ends_at'])).isoformat(),
                    'campaign_fingerprint':hashlib.sha256(canonical(campaign).encode()).hexdigest()}
                self.emit(c,identity,branch,kind,grant,key,digest)
                return {**{k:v for k,v in grant.items() if k!='key_hash'},'activation_key':raw}
            elif kind=='revoke_grant':
                grant=state['grants'].get(p['grant_id'])
                if not grant or grant['branch_id']!=branch:raise ERPError('Grant not found at this branch')
                identifier(p['reason'])
            elif kind=='reorder':
                if not c.execute('SELECT 1 FROM erp_items WHERE id=?',(p['item_id'],)).fetchone():raise ERPError('Unknown inventory item')
                for field in ['minimum','daily_target','weekly_target']:number(p[field],0,1000000000)
                if not p['minimum']<=p['daily_target']<=p['weekly_target']:raise ERPError('Require minimum <= daily target <= weekly target')
            elif kind=='tax':
                if identity['role']!='owner':raise PermissionError('Only owner sets the estimated tax scenario')
                number(p['rate_bps'],0,10000)
            return self.emit(c,identity,branch,kind,p,key,digest)
    def zone(self,state,branch,required=True):
        zone=state['settings'].get(branch,{}).get('timezone') or ('Europe/London' if self.erp.jurisdiction=='GB' else None)
        if not zone and required:raise ERPError('Configure branch IANA timezone before using attendance')
        return zone
    def employee(self,identity,state,branch):
        emp=state['employees'].get(identity.get('employee_id'))
        if not emp or emp['branch_id']!=branch:raise ERPError('User must be linked to a registered employee at this branch')
        return emp
    def shift_access(self,identity,state,branch,shift_id):
        shift=state['shifts'].get(shift_id)
        if not shift or shift['branch_id']!=branch:raise ERPError('Unknown shift for branch')
        if identity['role'] not in MANAGERS and shift['employee_id']!=identity.get('employee_id'):raise PermissionError('Cannot access another employee shift')
        return shift
    def shift_cash(self,c,state,shift):
        docs=[sale['document_id'] for sale in state['sales'] if sale.get('shift_id')==shift['shift_id']]
        delta=0
        for doc in docs:
            delta+=c.execute("SELECT COALESCE(SUM(debit-credit),0) FROM erp_lines WHERE document_id=? AND account='1000'",(doc,)).fetchone()[0]
        return shift['opening_cash_minor']+delta
    def promotion_context(self,state,branch,employee,activation_key,now):
        if not activation_key:return {}
        grant=next((v for v in state['grants'].values() if secrets.compare_digest(v['key_hash'],sign(self.key,activation_key))),None)
        if not grant or grant['used'] or grant.get('revoked') or grant['branch_id']!=branch or grant['employee_id']!=employee['employee_id'] or instant(grant['expires_at'])<=now:raise ERPError('Promotion key is invalid, used, expired or outside scope')
        campaign=state['campaigns'][grant['campaign_id']]
        if not campaign['enabled'] or not instant(campaign['starts_at'])<=now<instant(campaign['ends_at']) or hashlib.sha256(canonical(campaign).encode()).hexdigest()!=grant['campaign_fingerprint']:raise ERPError('Campaign changed or is no longer active')
        return {'discount_bps':campaign['discount_bps'],'promotion_id':campaign['campaign_id'],'grant_id':grant['grant_id']}
    def quote_order(self,identity,branch,items,activation_key=None):
        self.access(identity,branch)
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN');state=self.state(c);employee=self.employee(identity,state,branch)
            context=self.promotion_context(state,branch,employee,activation_key,self.now())
            return quote(catalog(c,state,branch),items,context.get('discount_bps',0))
    def sale(self,identity,payload,key,activation_key=None,order_id=None,order_revision=None,expected_gross_minor=None):
        branch=payload.get('branch_id');self.access(identity,branch)
        if payload.get('kind') not in ('sale','collect'):raise ERPError('Cashier endpoint accepts sale or collection')
        now=self.now()
        # For cashier workflows the accounting date comes from server-local business date.
        def prepare(c,p):
            state=self.state(c);employee=self.employee(identity,state,branch)
            shift=next((s for s in state['shifts'].values() if s['employee_id']==employee['employee_id'] and not s['ended_at']),None)
            if not shift or shift['branch_id']!=branch:raise ERPError('Open an employee shift before checkout')
            if not shift.get('opening_confirmed'):raise ERPError('Confirm opening till cash before checkout')
            if p['date']!=now.astimezone(ZoneInfo(shift['timezone'])).date().isoformat():raise ERPError('POS date must match current business date')
            context={'shift_id':shift['shift_id'],'receipt_profile':state['receipt_profiles'].get(branch,{})}
            if p['kind']=='sale':
                if order_id:
                    order=state['orders'].get(order_id)
                    if not order or order['branch_id']!=branch or order['paid'] or order['revision']!=order_revision or order['items']!=p['items']:raise ERPError('Table order changed or already paid')
                    context.update(order_id=order_id,table_id=order['table_id'])
                menu=catalog(c,state,branch);context['catalog']={id:dict(v) for id,v in menu.items() if v['active']}
                if not isinstance(p.get('items'),list):raise ERPError('Order items required')
                for item in p['items']:
                    if isinstance(item,dict) and isinstance(item.get('product_id'),str) and item['product_id'] in context['catalog']:
                        context['catalog'][item['product_id']]['recipe']=recipe(menu,item['product_id'])

            if activation_key and p['kind']!='sale':raise ERPError('Promotions apply only to new sales')
            context.update(self.promotion_context(state,branch,employee,activation_key,now))
            if p['kind']=='sale':
                context['pos_quote']=quote(context['catalog'],p['items'],context.get('discount_bps',0))
                if expected_gross_minor is not None and number(expected_gross_minor,0)!=context['pos_quote']['gross_minor']:raise ERPError('Price changed; review the updated total before checkout')
            return context
        def finalize(c,doc,p,context):
            self.emit(c,identity,branch,'sale',{'document_id':doc,'shift_id':context['shift_id'],'grant_id':context.get('grant_id'),'order_id':context.get('order_id')},'checkout:'+doc)
        return self.erp.post(payload,key,identity['user_id'],identity['role'],prepare,finalize,{'actor':identity['user_id'],'promotion_hash':sign(self.key,activation_key) if activation_key else None,'order_id':order_id,'order_revision':order_revision,'expected_gross_minor':expected_gross_minor})
    def split_shift(self,shift):
        if not shift.get('ended_at'):return []
        start=instant(shift['started_at']);end=instant(shift['ended_at']);zone=ZoneInfo(shift['timezone']);parts=[];cursor=start
        while cursor<end:
            local=cursor.astimezone(zone);midnight=datetime.combine(local.date()+timedelta(days=1),time(),zone).astimezone(UTC)
            boundary=min(end,midnight);seconds=int((boundary-cursor).total_seconds());parts.append([local.date().isoformat(),seconds]);cursor=boundary
        total=sum(x[1] for x in parts);paid=shift['paid_seconds']
        allocated=[paid*seconds//total if total else 0 for _,seconds in parts];remainder=paid-sum(allocated)
        for i in sorted(range(len(parts)),key=lambda i:(paid*parts[i][1]%total),reverse=True)[:remainder]:allocated[i]+=1
        return [{'date':d,'paid_seconds':allocated[i],'hourly_minor':shift['hourly_minor'],'shift_id':shift['shift_id'],'employee_id':shift['employee_id']} for i,(d,_) in enumerate(parts)]
    def payroll(self,state,branch,month,employee_id=None):
        period(month);rows={};blocked=[];shift_ids=set()
        for shift in state['shifts'].values():
            if shift['branch_id']!=branch or (employee_id and shift['employee_id']!=employee_id):continue
            # An open shift touching the period prevents finalising the payroll.
            if not shift['ended_at']:
                if instant(shift['started_at']).astimezone(ZoneInfo(shift['timezone'])).strftime('%Y-%m')<=month:blocked.append(shift['shift_id'])
                continue
            portions=[p for p in self.split_shift(shift) if p['date'].startswith(month)]
            if not portions:continue
            if not shift.get('reviewed'):blocked.append(shift['shift_id'])
            for part in portions:
                row=rows.setdefault(part['employee_id'],{'employee_id':part['employee_id'],'name':shift['employee_name'],'paid_seconds':0,'gross_fraction':Fraction(0),'days':{}})
                row['paid_seconds']+=part['paid_seconds'];row['gross_fraction']+=Fraction(part['paid_seconds']*part['hourly_minor'],3600)
                row['days'][part['date']]=row['days'].get(part['date'],0)+part['paid_seconds'];shift_ids.add(part['shift_id'])
        output=[]
        for row in rows.values():
            exact=row.pop('gross_fraction');row['gross_minor']=round(exact);output.append(row)
        return {'month':month,'employees':output,'gross_minor':sum(r['gross_minor'] for r in output),'blocked_shift_ids':sorted(set(blocked)),
            'shift_ids':sorted(shift_ids),'accrued':state['payrolls'].get((branch,month)),
            'basis':'Gross hourly pay only; no overtime, holiday, pension, NI, income-tax or statutory payroll deductions'}
    def accrue_payroll(self,identity,branch,month,day,key):
        self.access(identity,branch,True);period(month);iso(day)
        if not day.startswith(month):raise ERPError('Payroll accrual date must be in the selected payroll month')
        def prepare(c,p):
            state=self.state(c)
            if (branch,month) in state['payrolls']:raise ERPError('Payroll month already accrued')
            cutoff=datetime.combine(date.fromisoformat(month+'-01')+timedelta(days=monthrange(int(month[:4]),int(month[5:]))[1]),time(),ZoneInfo(self.zone(state,branch))).astimezone(UTC)
            if self.now()<cutoff:raise ERPError('Finish the payroll month before final accrual')
            pay=self.payroll(state,branch,month)
            if pay['blocked_shift_ids'] or not pay['employees']:raise ERPError('Review and close all shifts before payroll accrual')
            if pay['gross_minor']!=p['net_minor']:raise ERPError('Payroll changed; retry using the refreshed amount')
            return {'payroll_id':uuid.uuid4().hex,'month':month,'pay':pay}
        # Snapshot only provides payload; prepare rechecks inside the financial transaction.
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN');pay=self.payroll(self.state(c),branch,month)
        payload={'kind':'expense','branch_id':branch,'date':day,'category':'labor','net_minor':pay['gross_minor'],'tax_minor':0,'payment':'credit'}
        def finalize(c,doc,p,ctx):
            self.emit(c,identity,branch,'payroll',{'payroll_id':ctx['payroll_id'],'month':month,'document_id':doc,'gross_minor':p['net_minor'],'shift_ids':ctx['pay']['shift_ids']},'payroll:'+doc)
        return self.erp.post(payload,key,identity['user_id'],identity['role'],prepare,finalize)
    def session(self,identity,branch,auto_start=True):
        self.access(identity,branch)
        shift=None
        if auto_start and identity.get('employee_id') and identity['role'] in ('cashier','manager'):
            shift=self.action(identity,branch,'shift_open',{},'auto:'+uuid.uuid4().hex)
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN');state=self.state(c)
            if identity['role']=='cashier':self.employee(identity,state,branch)
            mine=[s for s in state['shifts'].values() if s['branch_id']==branch and s['employee_id']==identity.get('employee_id')]
            return {'user_id':identity['user_id'],'name':identity.get('name'),'role':identity['role'],'employee_id':identity.get('employee_id'),
                'branches':identity['branches'],'branch_id':branch,'currency':self.erp.currency,'minor_digits':0 if self.erp.currency=='VND' else 2,
                'receipt_profile':state['receipt_profiles'].get(branch,{}),'server_now':self.now().isoformat(),'timezone':self.zone(state,branch,False),'active_shift':next((s for s in mine if not s['ended_at']),None),'my_shifts':mine,
                'handover_recipients':[{'employee_id':e['employee_id'],'name':e['name']} for e in state['employees'].values() if e['branch_id']==branch and e['employee_id']!=identity.get('employee_id')],
                'catalog':[{k:v for k,v in p.items() if k!='recipe'} for p in catalog(c,state,branch).values()],
                'tables':[p for (b,id),p in state['tables'].items() if b==branch],
                'orders':[p for p in state['orders'].values() if p['branch_id']==branch and not p['paid']],'campaigns':[{k:v for k,v in p.items()} for p in state['campaigns'].values() if p['branch_id']==branch]}
    def shift_summary(self,identity,branch):
        self.access(identity,branch)
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN');state=self.state(c);records=[]
            for shift in state['shifts'].values():
                if shift['branch_id']!=branch or (identity['role']=='cashier' and shift['employee_id']!=identity.get('employee_id')):continue
                own=[s for s in state['sales'] if s.get('shift_id')==shift['shift_id']]
                sales=[]
                for sale in own:
                    row=c.execute('SELECT id,kind,payload,business_date FROM erp_documents WHERE id=?',(sale['document_id'],)).fetchone()
                    if not row:raise IntegrityError('Shift transaction missing')
                    data=json.loads(row['payload']);computed=dict(data.get('computed',{}))
                    if identity['role']=='cashier':computed.pop('cost_minor',None)
                    sales.append({'document_id':row['id'],'kind':row['kind'],'date':row['business_date'],**computed})
                records.append({**shift,'expected_cash_minor':self.shift_cash(c,state,shift),'sales':sales,'daily_hours':self.split_shift(shift)})
            return {'server_now':self.now().isoformat(),'currency':self.erp.currency,'shifts':records}
    def receipt(self,identity,doc_id):
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN');state=self.state(c)
            row=c.execute("SELECT * FROM erp_documents WHERE id=? AND kind='sale'",(doc_id,)).fetchone()
            if not row:raise ERPError('Sale document not found')
            self.access(identity,row['branch_id'])
            if identity['role']=='cashier':
                link=next((s for s in state['sales'] if s['document_id']==doc_id),None)
                if not link or state['shifts'][link['shift_id']]['employee_id']!=identity.get('employee_id'):raise PermissionError('Receipt belongs to another cashier')
            return {'document_id':doc_id,'date':row['business_date'],'branch_id':row['branch_id'],'currency':self.erp.currency,
                'receipt_type':'Non-fiscal sales receipt; not a certified VAT invoice',**{k:v for k,v in json.loads(row['payload'])['computed'].items() if k not in ('cost_minor','shift_id')}}
    def management(self,identity,branch,month,day=None,connection=None):
        self.access(identity,branch,True);period(month);day=iso(day) if day else None
        with (closing(self.erp.connect()) if connection is None else nullcontext(connection)) as c:
            if connection is None:c.execute('BEGIN')
            state=self.state(c);catalog_data=catalog(c,state,branch).values();table_data=[p for (b,id),p in state['tables'].items() if b==branch];pay=self.payroll(state,branch,month)
            open_table_ids=sorted({o['table_id'] for o in state['orders'].values() if o['branch_id']==branch and not o.get('paid')})
            employees=[p for p in state['employees'].values() if p['branch_id']==branch]
            shifts=[p for p in state['shifts'].values() if p['branch_id']==branch]
            purchases=[]
            for row in c.execute("SELECT id,business_date,payload FROM erp_documents WHERE branch_id=? AND kind='purchase' ORDER BY business_date,rowid",(branch,)):
                payload=json.loads(row['payload']);purchases.append({'document_id':row['id'],'date':row['business_date'],**payload,'price_per_kg_minor':round(Fraction(payload['net_minor']*1000,payload['quantity']))})
            policies={item:policy for (b,item),policy in state['reorders'].items() if b==branch}
            campaigns=[p for p in state['campaigns'].values() if p['branch_id']==branch]
            grants=[{k:v for k,v in p.items() if k!='key_hash'} for p in state['grants'].values() if p['branch_id']==branch]
            zone=self.zone(state,branch,False);tax=state['tax'].get(branch);receipt_profile=state['receipt_profiles'].get(branch,{})
            day=day or (self.now().astimezone(ZoneInfo(zone)) if zone else self.now()).date().isoformat()
            last=month+f'-{monthrange(int(month[:4]),int(month[5:]))[1]:02d}'
            financial=self.erp.report(branch,month+'-01',last,connection=c);daily=self.erp.report(branch,day,day,connection=c)
        stock=daily['stock'];shopping=[]
        for item in stock:
            policy=policies.get(item['item_id'])
            if policy:
                shopping.append({'item_id':item['item_id'],'name':item['name'],'current_quantity':item['quantity'],'unit':item['unit'],
                    'today_buy':max(0,policy['daily_target']-item['quantity']) if item['quantity']<policy['minimum'] else 0,
                    'week_buy':max(0,policy['weekly_target']-item['quantity']),**policy})
        day_parts=[part for shift in shifts for part in self.split_shift(shift) if part['date']==day]
        daily_gross=round(sum((Fraction(part['paid_seconds']*part['hourly_minor'],3600) for part in day_parts),Fraction(0)))
        posted_on_day=sum(doc['payload'].get('net_minor',0) for doc in daily['documents'] if doc['business_date']==day and doc['payload'].get('computed',{}).get('payroll_id'))
        estimated_daily_profit=daily['pnl']['profit_before_interest_tax_minor']+posted_on_day-daily_gross
        purchases=[purchase for purchase in purchases if purchase['date']<=day]
        before=financial['pnl']['profit_before_interest_tax_minor'];tax_estimate=max(0,before)*tax['rate_bps']//10000 if tax else None
        return {'currency':self.erp.currency,'minor_digits':0 if self.erp.currency=='VND' else 2,'branch_id':branch,'month':month,'day':day,'timezone':zone,
            'receipt_profile':receipt_profile,'catalog':list(catalog_data),'tables':table_data,'financial':financial,'daily':daily,'payroll':pay,'employees':employees,'shifts':shifts,'purchases':purchases,'shopping':shopping,'campaigns':campaigns,'grants':grants,
            'open_table_ids':open_table_ids,
            'daily_gross_hours_minor':daily_gross,'estimated_daily_profit_after_hours_minor':estimated_daily_profit,
            'estimated_tax_minor':tax_estimate,'estimated_after_tax_minor':None if tax_estimate is None else before-tax_estimate,
            'tax_basis':'Owner-configured scenario only; not statutory corporation-tax calculation',
            'unposted_payroll_gross_minor':0 if pay['accrued'] else pay['gross_minor'],
            'staffing_notice':'Inactive dates stop new check-ins only. Past shifts and wages remain payable. Staffing changes affect costs/profit, not sales revenue.'}
    def owner_summary(self,identity,month):
        if identity['role']!='owner':raise PermissionError('Owner workspace only')
        period(month)
        with closing(self.erp.connect()) as c:
            c.execute('BEGIN')
            reports=[self.management(identity,branch,month,connection=c) for branch in identity.get('branches',[])]
        revenue=sum(r['financial']['pnl']['revenue_minor'] for r in reports);before=sum(r['financial']['pnl']['profit_before_interest_tax_minor'] for r in reports)
        all_tax=bool(reports) and all(r['estimated_tax_minor'] is not None for r in reports)
        return {'currency':self.erp.currency,'month':month,'branches':reports,'revenue_minor':revenue,'before_tax_minor':before,
            'estimated_after_tax_minor':sum(r['estimated_after_tax_minor'] for r in reports) if all_tax else None,
            'estimated_tax_minor':sum(r['estimated_tax_minor'] for r in reports) if all_tax else None}
