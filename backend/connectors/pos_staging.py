"""Stage mapped POS close exports without mixing currencies or accounting revenue.
This is an export-contract adapter, not a native L'Addition API client.
"""
import argparse
import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from backend.pipeline.runner import atomic_json, read_records

FIELDS = ['restaurant_id','close_id','business_date','currency','net_sales','tax','gross_sales','status']
VERSION = 'pos-export-1'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS sync_runs(
 id TEXT PRIMARY KEY, provider TEXT, company_id TEXT, source_id TEXT,
 file_hash TEXT, config_hash TEXT, status TEXT, row_count INTEGER DEFAULT 0,
 error TEXT, started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT);
CREATE TABLE IF NOT EXISTS closes(
 provider TEXT NOT NULL, company_id TEXT NOT NULL, restaurant_id TEXT NOT NULL,
 close_id TEXT NOT NULL, business_date TEXT NOT NULL, currency TEXT NOT NULL,
 net_minor INTEGER NOT NULL, tax_minor INTEGER NOT NULL, gross_minor INTEGER NOT NULL,
 source_id TEXT NOT NULL, run_id TEXT NOT NULL, source_row INTEGER NOT NULL,
 branch_id TEXT NOT NULL,
 PRIMARY KEY(provider,company_id,restaurant_id,close_id));
CREATE TABLE IF NOT EXISTS active_sources(
 provider TEXT, company_id TEXT, source_id TEXT, file_hash TEXT, config_hash TEXT,
 PRIMARY KEY(provider,company_id,source_id));
'''

def money(value, currency, decimal_separator):
    digits = {'EUR':2,'VND':0}.get(currency)
    if digits is None: raise ValueError('Unsupported currency; add explicit minor-unit policy')
    text = str(value).strip()
    if decimal_separator == ',':
        if '.' in text: raise ValueError('Dot not allowed in comma-decimal contract')
        text=text.replace(',','.')
    elif ',' in text: raise ValueError('Comma not allowed in dot-decimal contract')
    try: amount=Decimal(text)
    except InvalidOperation as exc: raise ValueError('Invalid money') from exc
    scaled=amount*(10**digits)
    if not scaled.is_finite() or scaled!=scaled.to_integral_value() or abs(scaled)>9_000_000_000_000_000:
        raise ValueError('Invalid money precision/range')
    return int(scaled)

def normalize(headers, records, config):
    mapping=config['columns']
    if set(mapping)!=set(FIELDS) or len(set(mapping.values()))!=len(FIELDS):
        raise ValueError('Map every POS canonical field exactly once')
    if not set(mapping.values()).issubset(headers): raise ValueError('Missing mapped columns')
    if not records:raise ValueError('Empty batch not published')
    valid,errors,seen=[],[],set()
    for number,record in enumerate(records,2):
        try:
            row={k:record[mapping[k]] for k in FIELDS}
            for k in ['restaurant_id','close_id','currency','status']:
                if row[k] is None or not str(row[k]).strip():raise ValueError('Missing '+k)
                row[k]=str(row[k]).strip()
            if row['status']!=config['closed_status']:raise ValueError('Only finalized POS closes are eligible')
            branch=config['restaurants'].get(row['restaurant_id'])
            if not branch:raise ValueError('Restaurant must be mapped to branch')
            d=row['business_date']
            if isinstance(d,datetime):
                if d.time().isoformat()!='00:00:00':raise ValueError('Business date must be date-only')
                d=d.date()
            d=d.isoformat() if isinstance(d,date) else str(d)
            if date.fromisoformat(d).isoformat()!=d:raise ValueError('Use ISO business date')
            row['business_date']=d
            key=(row['restaurant_id'],row['close_id'])
            if key in seen:raise ValueError('Duplicate close id')
            seen.add(key)
            amounts=[money(row[k],row['currency'],config['decimal_separator']) for k in ['net_sales','tax','gross_sales']]
            if amounts[0]+amounts[1]!=amounts[2]:raise ValueError('Net sales + tax does not equal gross sales')
            valid.append((number,row,branch,amounts))
        except (ValueError,TypeError,KeyError) as exc:
            errors.append({'row':number,'error':str(exc)})
    return valid,errors

def stage(file,root,config_file,source_id,replace=False):
    root=Path(root);file=Path(file);config=json.loads(Path(config_file).read_text())
    if config.get('schema_version')!=1:raise ValueError('Unsupported connector contract version')
    if config.get('decimal_separator') not in ('.',','):raise ValueError('Specify decimal_separator')
    if not source_id.strip() or not config.get('provider') or not config.get('company_id'):raise ValueError('Source/provider/company required')
    for name in ['bronze','silver','quarantine','reports']:(root/name).mkdir(parents=True,exist_ok=True)
    if file.stat().st_size>config['max_bytes']:raise ValueError('File too large')
    payload=file.read_bytes();sha=hashlib.sha256(payload).hexdigest()
    cfg=hashlib.sha256(json.dumps({'version':VERSION,'config':config},sort_keys=True).encode()).hexdigest()
    run_id=uuid.uuid4().hex;identity=(config['provider'],config['company_id'],source_id)
    db=sqlite3.connect(root/'connectors.sqlite3');db.executescript(SCHEMA)
    try:
        with db:db.execute('INSERT INTO sync_runs(id,provider,company_id,source_id,file_hash,config_hash,status) VALUES(?,?,?,?,?,?,?)',(run_id,*identity,sha,cfg,'running'))
        if file.suffix.lower() not in ('.csv','.xlsx'):raise ValueError('POS staging accepts CSV/XLSX, not scanned invoices')
        bronze=root/'bronze'/(sha+file.suffix.lower())
        if bronze.exists():
            if hashlib.sha256(bronze.read_bytes()).hexdigest()!=sha:raise ValueError('Bronze checksum mismatch')
        else:
            with bronze.open('xb') as handle:handle.write(payload)
        headers,records=read_records(payload,file.suffix.lower(),config)
        valid,errors=normalize(headers,records,config)
        if errors:
            atomic_json(root/'quarantine'/(run_id+'.json'),{'run_id':run_id,'errors':errors,'file_hash':sha})
            raise ValueError('Invalid batch; inspect quarantine/'+run_id+'.json')
        atomic_json(root/'silver'/(run_id+'.json'),{'file_hash':sha,'config_hash':cfg,'provider':identity[0],
            'company_id':identity[1],'source_id':source_id,'rows':[{'source_row':n,'branch_id':b,**r,
                'net_minor':a[0],'tax_minor':a[1],'gross_minor':a[2]} for n,r,b,a in valid]})
        with db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute('SELECT file_hash,config_hash FROM active_sources WHERE provider=? AND company_id=? AND source_id=?',identity).fetchone()
            if active==(sha,cfg):
                db.execute("UPDATE sync_runs SET status='skipped',finished_at=CURRENT_TIMESTAMP WHERE id=?",(run_id,))
                return {'status':'skipped','run_id':run_id,'gold_changed':False}
            if active and not replace:raise ValueError('Revision requires explicit --replace for same source-id')
            if active:db.execute('DELETE FROM closes WHERE provider=? AND company_id=? AND source_id=?',identity)
            for number,row,branch,amounts in valid:
                db.execute('INSERT INTO closes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (identity[0],identity[1],row['restaurant_id'],row['close_id'],row['business_date'],row['currency'],*amounts,source_id,run_id,number,branch))
            db.execute('INSERT OR REPLACE INTO active_sources VALUES(?,?,?,?,?)',(*identity,sha,cfg))
            db.execute("UPDATE sync_runs SET status='staged',row_count=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(len(valid),run_id))
        return {'status':'staged','run_id':run_id,'rows':len(valid),'gold_changed':False,
            'note':'POS staging only. Reconcile with accounting and select revenue source before Gold publication.'}
    except Exception as exc:
        db.rollback()
        with db:db.execute("UPDATE sync_runs SET status='failed',error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(str(exc),run_id))
        raise
    finally:db.close()

def preview(root):
    db=sqlite3.connect(Path(root)/'connectors.sqlite3');db.row_factory=sqlite3.Row
    try:
        return [dict(row) for row in db.execute('''SELECT provider,company_id,branch_id,substr(business_date,1,7) month,currency,
            SUM(net_minor) net_minor,SUM(tax_minor) tax_minor,SUM(gross_minor) gross_minor,COUNT(*) closes
            FROM closes GROUP BY provider,company_id,branch_id,substr(business_date,1,7),currency ORDER BY month,currency,branch_id''')]
    finally:db.close()

def reconcile(pos,ledger):
    """Compare source totals; never add ERP revenue to POS revenue. Exact minor units."""
    totals=[]
    for dataset in (pos,ledger):
        grouped=defaultdict(int)
        for row in dataset:
            key=(row['branch_id'],row['month'],row['currency'])
            if type(row['net_minor']) is not int:raise ValueError('Integer minor-unit totals required')
            grouped[key]+=row['net_minor']
        totals.append(grouped)
    output=[]
    for key in sorted(set(totals[0])|set(totals[1])):
        left,right=totals[0].get(key),totals[1].get(key)
        delta=None if left is None or right is None else left-right
        output.append(dict(zip(['branch_id','month','currency'],key),pos_net_minor=left,ledger_net_minor=right,
            delta_minor=delta,status='missing_source' if delta is None else 'matched' if delta==0 else 'review_required'))
    return output

def main():
    p=argparse.ArgumentParser(description='Stage normalized POS export contract; NOT a live vendor API connector')
    p.add_argument('file');p.add_argument('--config',required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--root',default='backend/data/connector_staging');p.add_argument('--replace',action='store_true')
    args=p.parse_args();result=stage(args.file,args.root,args.config,args.source_id,args.replace)
    result['monthly_preview']=preview(args.root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
