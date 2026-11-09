"""Transactional restaurant operations. Integer minor units, one ledger currency.
Tax amounts are supplied explicitly, not a statutory tax engine.
"""
import hashlib
import json
import sqlite3
import uuid
from datetime import date
from contextlib import closing
from pathlib import Path
from backend.integrity import key_from_env
from backend.erp.audit import initialize_baseline,append,verify_ledger

ACCOUNTS=[('1000','Tiền mặt','asset'),('1010','Ngân hàng','asset'),('1100','Phải thu khách hàng','asset'),
 ('1200','Kho nguyên liệu','asset'),('1300','Thuế đầu vào chờ đối soát','asset'),('1500','Tài sản thiết bị','asset'),
 ('1590','Khấu hao lũy kế','contra_asset'),('2000','Phải trả nhà cung cấp','liability'),('2100','Thuế đầu ra chờ đối soát','liability'),
 ('3000','Vốn góp','equity'),('4000','Doanh thu thuần','income'),('5000','Giá vốn món ăn','expense'),
 ('5100','Nhân sự','expense'),('5200','Thuê mặt bằng','expense'),('5300','Vận hành khác','expense'),('5400','Khấu hao','expense')]
ALLOWED={'owner':{'capital','purchase','sale','collect','pay','expense','asset','depreciate','reserve','reverse_expense','close_period'},
 'manager':{'sale','collect','purchase','pay','expense','asset','depreciate','close_period'},
 'accountant':{'purchase','collect','pay','expense','asset','depreciate','reverse_expense','close_period'},'cashier':{'sale','collect'}}

class ERPError(ValueError): pass

def number(value,minimum=1,maximum=1_000_000_000_000):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ERPError(f'Expected integer in range {minimum}..{maximum}')
    return value

def iso(value):
    try:
        if date.fromisoformat(value).isoformat()!=value:raise ValueError()
    except (ValueError,TypeError):raise ERPError('Date must use YYYY-MM-DD')
    return value

class ERP:
    def __init__(self,path,currency='GBP',jurisdiction='GB',audit_key=None):
        self.audit_key=audit_key if audit_key is not None else key_from_env()
        if not isinstance(self.audit_key,bytes) or len(self.audit_key)<32:raise ERPError('Audit key must contain at least 32 bytes')
        if currency not in ('GBP','EUR','VND'):raise ERPError('Supported ledger currencies: GBP, EUR, VND')
        if not isinstance(jurisdiction,str) or len(jurisdiction)!=2 or not jurisdiction.isalpha():raise ERPError('Two-letter jurisdiction required')
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as c, c:
            c.executescript(Path(__file__).with_name('schema.sql').read_text())
            c.executescript(Path(__file__).with_name('integrity_schema.sql').read_text())
            old=c.execute("SELECT value FROM erp_meta WHERE key='currency'").fetchone()
            if old and old[0]!=currency:raise ERPError('Cannot change ledger currency; create a separate ledger')
            c.execute("INSERT OR IGNORE INTO erp_meta VALUES('currency',?)",(currency,))
            old_country=c.execute("SELECT value FROM erp_meta WHERE key='jurisdiction'").fetchone()
            if old_country and old_country[0]!=jurisdiction.upper():raise ERPError('Create a separate ledger for a different jurisdiction')
            c.execute("INSERT OR IGNORE INTO erp_meta VALUES('jurisdiction',?)",(jurisdiction.upper(),))
            c.executemany('INSERT OR IGNORE INTO erp_accounts VALUES(?,?,?)',ACCOUNTS)
            c.executemany('INSERT OR IGNORE INTO erp_branches VALUES(?,?)',[('q1','Bếp Trung Tâm'),('td','Bếp Bờ Sông'),('dn','Bếp Biển')])
            c.executemany('INSERT OR IGNORE INTO erp_items VALUES(?,?,?)',[('rice','Gạo','g'),('chicken','Thịt gà','g')])
            c.execute("INSERT OR IGNORE INTO erp_products VALUES('rice_chicken','Cơm gà',1200)")
            c.executemany("INSERT OR IGNORE INTO erp_recipes VALUES('rice_chicken',?,?)",[('rice',100),('chicken',150)])
            initialize_baseline(c,self.audit_key)
        self.currency=currency;self.jurisdiction=jurisdiction.upper()
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10,isolation_level='DEFERRED');c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
    def balance(self,c,account,branch,asof='9999-12-31'):
        return c.execute('SELECT COALESCE(SUM(l.debit-l.credit),0) FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id WHERE l.account=? AND d.branch_id=? AND d.business_date<=?',(account,branch,asof)).fetchone()[0]
    def liquid_guard(self,c,account,branch,amount,business_date):
        if self.balance(c,account,branch,business_date)<amount:raise ERPError('Insufficient funds in the payment account on the posting date')
    def remaining(self,c,doc_id):
        row=c.execute('SELECT due_minor FROM erp_documents WHERE id=?',(doc_id,)).fetchone()
        if not row:raise ERPError('Document not found')
        reversed_=c.execute('SELECT 1 FROM erp_documents WHERE reverses_id=?',(doc_id,)).fetchone()
        if reversed_:return 0
        paid=c.execute('SELECT COALESCE(SUM(amount_minor),0) FROM erp_settlements WHERE invoice_id=?',(doc_id,)).fetchone()[0]
        return row[0]-paid
    def post(self,payload,request_key,actor='local-owner',role='owner',prepare=None,finalize=None,request_scope=None):
        if not isinstance(payload,dict):raise ERPError('JSON object required')
        if not isinstance(request_key,str) or not request_key.strip() or not 1<=len(request_key)<=150:raise ERPError('Idempotency-Key required, max 150 chars')
        p=json.loads(json.dumps(payload))
        for key in ['kind','branch_id','date','payment','category','item_id','invoice_id','asset_id','document_id','name']:
            if key in p and not isinstance(p[key],str):raise ERPError('Invalid text field: '+key)
        kind=p.get('kind');branch=p.get('branch_id');day=iso(p.get('date'))
        if kind not in ALLOWED.get(role,set()):raise PermissionError('This role cannot perform the transaction')
        fields={'capital':{'amount_minor','payment'},'purchase':{'item_id','quantity','net_minor','tax_minor','payment'},
            'sale':{'items','tax_minor','payment'},'collect':{'invoice_id','amount_minor','payment'},'pay':{'invoice_id','amount_minor','payment'},
            'expense':{'category','net_minor','tax_minor','payment'},'asset':{'name','net_minor','tax_minor','life_months','payment'},
            'depreciate':{'asset_id'},'reserve':{'target_minor'},'reverse_expense':{'document_id'},'close_period':set()}
        if set(p)-({'kind','branch_id','date'}|fields[kind]):raise ERPError('Unsupported fields in transaction payload')
        digest=hashlib.sha256(json.dumps({'payload':p,'scope':request_scope} if request_scope is not None else p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            verify_ledger(c,self.audit_key)
            old=c.execute('SELECT id,payload_hash FROM erp_documents WHERE request_key=?',(request_key,)).fetchone()
            if old:
                if old['payload_hash']!=digest:raise ERPError('Idempotency key was already used for a different payload')
                c.rollback();return {'document_id':old['id'],'status':'already_posted'}
            if not c.execute('SELECT 1 FROM erp_branches WHERE id=?',(branch,)).fetchone():raise ERPError('Invalid branch')
            if c.execute('SELECT 1 FROM erp_periods WHERE branch_id=? AND month=?',(branch,day[:7])).fetchone():raise ERPError('The accounting period is closed')
            context=prepare(c,p) if prepare else {}
            latest=c.execute("SELECT MAX(business_date) FROM erp_documents WHERE branch_id=? AND kind NOT IN ('reserve','close_period')",(branch,)).fetchone()[0]
            if latest and day<latest and kind not in ('reserve','close_period') and not (kind=='expense' and context.get('payroll_id')):raise ERPError('Transactions must be posted in chronological order. Use an adjustment for an earlier date.')
            doc=uuid.uuid4().hex;lines=[];moves=[];asset=None;dep=None;settle=None;reverse=None;due=0
            def line(account,debit=0,credit=0):
                if debit or credit:lines.append((account,debit,credit))
            def funding_account(default='bank'):
                key=p.get('payment',default)
                mapping={'cash':'1000','bank':'1010','credit':'2000'}
                if key not in mapping:raise ERPError('Invalid payment method')
                return mapping[key]
            def stock(item,qty,value):
                if not c.execute('SELECT 1 FROM erp_items WHERE id=?',(item,)).fetchone():raise ERPError('Invalid ingredient')
                c.execute('INSERT OR IGNORE INTO erp_stock VALUES(?,?,0,0)',(branch,item))
                c.execute('UPDATE erp_stock SET quantity=quantity+?,value_minor=value_minor+? WHERE branch_id=? AND item_id=?',(qty,value,branch,item))
                moves.append((item,qty,value))
            if kind=='capital':
                amount=number(p.get('amount_minor'));account=funding_account()
                if account=='2000':raise ERPError('Capital contributions must go to cash or bank')
                line(account,amount);line('3000',credit=amount)
            elif kind in ('purchase','expense','asset'):
                net=number(p.get('net_minor'));tax=number(p.get('tax_minor',0),0);gross=net+tax;account=funding_account('credit' if kind=='purchase' else 'bank')
                if account!='2000':self.liquid_guard(c,account,branch,gross,day)
                else:due=gross
                if kind=='purchase':
                    item=p.get('item_id');qty=number(p.get('quantity'),maximum=1_000_000_000)
                    stock(item,qty,net);debit_account='1200'
                elif kind=='expense':
                    if role=='manager' and p.get('category')=='labor' and not context.get('payroll_id'):raise PermissionError('Use reviewed payroll accrual for manager salary postings')
                    debit_account={'rent':'5200','labor':'5100','other':'5300'}.get(p.get('category'))
                    if not debit_account:raise ERPError('Invalid expense category')
                else:
                    months=number(p.get('life_months'),1,600)
                    if months>net:raise ERPError('Asset cost in minor units must cover the selected depreciation months')
                    name=str(p.get('name','')).strip()
                    if not name or len(name)>160:raise ERPError('Asset name is required and must be at most 160 characters')
                    asset=(doc,doc,name,net,months);debit_account='1500'
                line(debit_account,net);line('1300',tax);line(account,credit=gross)
            elif kind=='sale':
                order=p.get('items')
                if not isinstance(order,list) or not 1<=len(order)<=50:raise ERPError('An order must have between 1 and 50 items')
                needs={};net=0;sale_lines=[]
                for item in order:
                    if not isinstance(item,dict) or set(item)!={'product_id','quantity'} or not isinstance(item.get('product_id'),str):raise ERPError('Invalid order item')
                    product=(lambda p:(p['price_minor'],p['name']) if p else None)(context['catalog'].get(item['product_id'])) if 'catalog' in context else c.execute('SELECT price_minor,name FROM erp_products WHERE id=?',(item.get('product_id'),)).fetchone()
                    if not product:raise ERPError('Invalid menu item')
                    qty=number(item.get('quantity'),1,10000);net+=product[0]*qty
                    sale_lines.append({'product_id':item['product_id'],'name':product[1],'quantity':qty,'unit_price_minor':product[0],'subtotal_minor':product[0]*qty})
                    recipe=[(r['item_id'],r['quantity']) for r in context['catalog'][item['product_id']]['recipe']] if 'catalog' in context else c.execute('SELECT item_id,quantity FROM erp_recipes WHERE product_id=?',(item['product_id'],)).fetchall()
                    if not recipe and 'catalog' not in context:raise ERPError('The menu item has no recipe')
                    for ingredient in recipe:needs[ingredient[0]]=needs.get(ingredient[0],0)+ingredient[1]*qty
                cost=0
                for item,qty in needs.items():
                    available=c.execute('SELECT quantity,value_minor FROM erp_stock WHERE branch_id=? AND item_id=?',(branch,item)).fetchone()
                    if not available or available[0]<qty:raise ERPError('Insufficient ingredients to complete the sale')
                    value=available[1] if qty==available[0] else available[1]*qty//available[0]
                    stock(item,-qty,-value);cost+=value
                subtotal=net;discount_bps=number(context.get('discount_bps',0),0,10000)
                discount=net*discount_bps//10000;net-=discount
                tax=number(p.get('tax_minor',0),0);gross=net+tax
                if context.get('pos_quote'):
                    q=context['pos_quote'];net=q['net_minor'];tax=q['tax_minor'];gross=q['gross_minor'];sale_lines=q['sale_lines'];subtotal=q['subtotal_minor'];discount=q['discount_minor'];p['tax_minor']=tax
                method=p.get('payment','cash');account={'cash':'1000','bank':'1010','credit':'1100','ticket_restaurant':'1100'}.get(method)
                if not account:raise ERPError('Invalid sales payment method')
                due=gross if method in ('credit','ticket_restaurant') else 0
                p['computed']={'net_minor':net,'tax_minor':tax,'gross_minor':gross,'cost_minor':cost,'subtotal_minor':subtotal,'discount_minor':discount,'discount_bps':discount_bps,'sale_lines':sale_lines}
                if context.get('promotion_id'):p['computed']['promotion_id']=context['promotion_id']
                if context.get('table_id'):p['computed']['table_id']=context['table_id']
                if context.get('receipt_profile'):p['computed']['receipt_profile']=context['receipt_profile']
                p['computed']['payment_method']=method
                if context.get('shift_id'):p['computed']['shift_id']=context['shift_id']
                line(account,gross);line('4000',credit=net);line('2100',credit=tax);line('5000',cost);line('1200',credit=cost)
            elif kind in ('pay','collect'):
                reference=p.get('invoice_id');invoice=c.execute('SELECT * FROM erp_documents WHERE id=?',(reference,)).fetchone()
                if not invoice or invoice['branch_id']!=branch:raise ERPError('The document does not belong to this branch')
                if day<invoice['business_date']:raise ERPError('Payment cannot precede the document date')
                if kind=='pay' and invoice['kind'] not in ('purchase','expense','asset'):raise ERPError('Only purchase, expense, or asset documents can be paid')
                if kind=='collect' and invoice['kind']!='sale':raise ERPError('Collections apply to sales receivables only')
                amount=number(p.get('amount_minor'))
                if amount>self.remaining(c,reference):raise ERPError('Payment exceeds the outstanding balance')
                account=funding_account()
                if account=='2000':raise ERPError('Select a cash or bank account for payment')
                if kind=='pay':self.liquid_guard(c,account,branch,amount,day);line('2000',amount);line(account,credit=amount)
                else:line(account,amount);line('1100',credit=amount)
                settle=(doc,reference,amount)
            elif kind=='depreciate':
                asset_id=p.get('asset_id');row=c.execute('SELECT a.*,d.branch_id,d.business_date FROM erp_assets a JOIN erp_documents d ON a.document_id=d.id WHERE a.id=?',(asset_id,)).fetchone()
                if not row or row['branch_id']!=branch:raise ERPError('The asset does not belong to this branch')
                if day<row['business_date']:raise ERPError('The depreciation period has not started')
                latest_month=c.execute('SELECT MAX(month) FROM erp_depreciation WHERE asset_id=?',(asset_id,)).fetchone()[0]
                if latest_month:
                    year,month=map(int,latest_month.split('-'));expected=f'{year+(month==12):04d}-{month%12+1:02d}'
                else:expected=row['business_date'][:7]
                if day[:7]!=expected:raise ERPError('Post depreciation for each consecutive month starting with the purchase month')
                used=c.execute('SELECT COALESCE(SUM(amount_minor),0) FROM erp_depreciation WHERE asset_id=?',(asset_id,)).fetchone()[0]
                installments=c.execute('SELECT COUNT(*) FROM erp_depreciation WHERE asset_id=?',(asset_id,)).fetchone()[0]
                if installments>=row['life_months']:raise ERPError('The asset is fully depreciated')
                amount=row['cost_minor']//row['life_months']+(1 if installments<row['cost_minor']%row['life_months'] else 0)
                if amount<=0:raise ERPError('The asset is fully depreciated')
                dep=(asset_id,day[:7],doc,amount);line('5400',amount);line('1590',credit=amount)
            elif kind=='reserve':
                number(p.get('target_minor'),0)
                # Liquidity target, neither an expense nor a cash transfer.
            elif kind=='reverse_expense':
                ref=p.get('document_id');row=c.execute('SELECT * FROM erp_documents WHERE id=?',(ref,)).fetchone()
                if not row or row['kind']!='expense' or row['branch_id']!=branch:raise ERPError('Only expense documents in the same branch can be reversed')
                if day<row['business_date']:raise ERPError('The reversal date cannot precede the original date')
                if c.execute('SELECT 1 FROM erp_settlements WHERE invoice_id=?',(ref,)).fetchone():raise ERPError('Paid expenses require a separate refund workflow')
                if c.execute("SELECT 1 FROM erp_lines WHERE document_id=? AND account IN ('1000','1010')",(ref,)).fetchone():raise ERPError('Cash or bank expenses require a separate refund workflow')
                reverse=ref
                for row in c.execute('SELECT account,debit,credit FROM erp_lines WHERE document_id=?',(ref,)):line(row[0],row[2],row[1])
            elif kind=='close_period':
                # Exact day locks the corresponding branch month, not other branches.
                balance=c.execute('SELECT COALESCE(SUM(l.debit-l.credit),0) FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id WHERE d.branch_id=? AND substr(d.business_date,1,7)=?',(branch,day[:7])).fetchone()[0]
                if balance:raise ERPError('The ledger is out of balance')
                c.execute('INSERT INTO erp_periods(branch_id,month,closed_by) VALUES(?,?,?)',(branch,day[:7],actor))
            else:raise ERPError('Unsupported transaction')
            if sum(x[1] for x in lines)!=sum(x[2] for x in lines):raise ERPError('The journal entry is out of balance')
            if not lines and kind not in ('reserve','close_period'):raise ERPError('The journal entry is empty')
            if context.get('payroll_id'):p['computed']={'payroll_id':context['payroll_id'],'month':context['month'],'basis':'approved_gross_hourly_pay'}
            c.execute('INSERT INTO erp_documents(id,request_key,payload_hash,kind,business_date,branch_id,actor,payload,due_minor,reverses_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (doc,request_key,digest,kind,day,branch,actor,json.dumps(p,ensure_ascii=False),due,reverse))
            c.executemany('INSERT INTO erp_lines(document_id,account,debit,credit) VALUES(?,?,?,?)',[(doc,*x) for x in lines])
            c.executemany('INSERT INTO erp_stock_moves(document_id,item_id,quantity,value_minor) VALUES(?,?,?,?)',[(doc,*x) for x in moves])
            if settle:c.execute('INSERT INTO erp_settlements VALUES(?,?,?)',settle)
            if asset:c.execute('INSERT INTO erp_assets VALUES(?,?,?,?,?)',asset)
            if dep:c.execute('INSERT INTO erp_depreciation VALUES(?,?,?,?)',dep)
            append(c,self.audit_key,doc)
            if finalize:finalize(c,doc,p,context)
            c.commit();return {'document_id':doc,'status':'posted','debit_minor':sum(x[1] for x in lines),'credit_minor':sum(x[2] for x in lines)}
        except sqlite3.IntegrityError as exc:c.rollback();raise ERPError('Document conflict, duplicate depreciation period, or data constraint violation') from exc
        except Exception:c.rollback();raise
        finally:c.close()
    def report(self,branch='q1',start='0001-01-01',end='9999-12-31',connection=None):
        iso(start);iso(end)
        if start>end:raise ERPError('Start date must not be after end date')
        c=connection if connection is not None else self.connect()
        try:
            if connection is None:c.execute('BEGIN')
            integrity=verify_ledger(c,self.audit_key)
            if not c.execute('SELECT 1 FROM erp_branches WHERE id=?',(branch,)).fetchone():raise ERPError('Invalid branch')
            trial=[]
            for account,name,kind in ACCOUNTS:
                value=self.balance(c,account,branch,end)
                trial.append({'account':account,'name':name,'kind':kind,'debit_balance_minor':max(0,value),'credit_balance_minor':max(0,-value)})
            period={r[0]:r[1] for r in c.execute('SELECT l.account,SUM(l.debit-l.credit) FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id WHERE d.branch_id=? AND d.business_date BETWEEN ? AND ? GROUP BY l.account',(branch,start,end))}
            revenue=-period.get('4000',0);cost=sum(period.get(k,0) for k in ['5000','5100','5200','5300']);dep=period.get('5400',0)
            cash=self.balance(c,'1000',branch,end);bank=self.balance(c,'1010',branch,end)
            reserve=c.execute("SELECT payload FROM erp_documents WHERE branch_id=? AND kind='reserve' AND business_date<=? ORDER BY business_date DESC, rowid DESC LIMIT 1",(branch,end)).fetchone()
            target=json.loads(reserve[0])['target_minor'] if reserve else 0
            documents=[]
            for row in c.execute('SELECT * FROM erp_documents WHERE branch_id=? AND business_date<=? ORDER BY business_date,rowid',(branch,end)):
                record=dict(row);record['payload']=json.loads(record['payload']);record.pop('payload_hash');record.pop('request_key')
                settled=c.execute('SELECT COALESCE(SUM(s.amount_minor),0) FROM erp_settlements s JOIN erp_documents d ON d.id=s.document_id WHERE s.invoice_id=? AND d.business_date<=?',(row['id'],end)).fetchone()[0]
                reversed_=c.execute('SELECT 1 FROM erp_documents WHERE reverses_id=? AND business_date<=?',(row['id'],end)).fetchone()
                record['remaining_minor']=0 if reversed_ else row['due_minor']-settled
                record['lines']=[dict(x) for x in c.execute('SELECT account,debit,credit FROM erp_lines WHERE document_id=?',(row['id'],))]
                documents.append(record)
            stocks=[dict(r) for r in c.execute('SELECT m.item_id,i.name,i.unit,SUM(m.quantity) quantity,SUM(m.value_minor) value_minor FROM erp_stock_moves m JOIN erp_documents d ON d.id=m.document_id JOIN erp_items i ON i.id=m.item_id WHERE d.branch_id=? AND d.business_date<=? GROUP BY m.item_id',(branch,end))]
            assets=[]
            for row in c.execute('SELECT a.*,d.business_date FROM erp_assets a JOIN erp_documents d ON d.id=a.document_id WHERE d.branch_id=? AND d.business_date<=?',(branch,end)):
                amount=c.execute('SELECT COALESCE(SUM(p.amount_minor),0) FROM erp_depreciation p JOIN erp_documents d ON d.id=p.document_id WHERE p.asset_id=? AND d.business_date<=?',(row['id'],end)).fetchone()[0]
                assets.append({**dict(row),'depreciated_minor':amount,'net_book_minor':row['cost_minor']-amount})
            payroll_due=sum(doc['remaining_minor'] for doc in documents if doc['payload'].get('computed',{}).get('payroll_id'))
            total_payable=-self.balance(c,'2000',branch,end)
            return {'liabilities_breakdown':{'payroll_payable_minor':payroll_due,'other_payable_minor':total_payable-payroll_due},'integrity':integrity,'currency':self.currency,'jurisdiction':self.jurisdiction,'minor_digits':0 if self.currency=='VND' else 2,'branch_id':branch,'from':start,'as_of':end,
                'pnl':{'revenue_minor':revenue,'food_minor':period.get('5000',0),'labor_minor':period.get('5100',0),'rent_minor':period.get('5200',0),'other_minor':period.get('5300',0),'operating_profit_before_depreciation_minor':revenue-cost,'depreciation_minor':dep,'profit_before_interest_tax_minor':revenue-cost-dep},
                'liquidity':{'cash_minor':cash,'bank_minor':bank,'reserve_target_minor':target,'liquidity_after_reserve_minor':cash+bank-target},
                'trial_balance':trial,'balanced':sum(x['debit_balance_minor']-x['credit_balance_minor'] for x in trial)==0,
                'stock':stocks,'assets':assets,'documents':documents,
                'closed_periods':[dict(x) for x in c.execute('SELECT * FROM erp_periods WHERE branch_id=?',(branch,))]}
        finally:
            if connection is None:c.close()
