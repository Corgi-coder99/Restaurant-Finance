"""Explicit, signed monthly completeness review for the analytics ledger."""
from datetime import date,datetime,timezone
import hashlib
import re
from backend.integrity import canonical,sign,verify,key_from_env,IntegrityError

REVIEW_SCHEMA='''CREATE TABLE IF NOT EXISTS data_period_reviews(
 branch_id TEXT NOT NULL,month TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('complete','zero')),
 reviewer TEXT NOT NULL,data_hash TEXT NOT NULL,signature TEXT NOT NULL,approved_at TEXT NOT NULL,
 PRIMARY KEY(branch_id,month))'''

def month(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}',value):raise ValueError('Month must be YYYY-MM')
    date.fromisoformat(value+'-01');return value

def period_hash(conn,branch,period):
    records=[dict(row) for row in conn.execute('SELECT branch_id,document_id,line_number,recognized_date,category,amount_vnd,source FROM entries WHERE branch_id=? AND substr(recognized_date,1,7)=? ORDER BY document_id,line_number',(branch,period))]
    return hashlib.sha256(canonical(records).encode()).hexdigest(),len(records)

def review_period(conn,branch,period,status,reviewer):
    period=month(period)
    if period>=date.today().strftime('%Y-%m'):raise ValueError('Only completed calendar months may be approved')
    if status not in ('complete','zero') or not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('Status/reviewer required')
    if not conn.execute('SELECT 1 FROM branches WHERE id=?',(branch,)).fetchone():raise ValueError('Unknown branch')
    digest,count=period_hash(conn,branch,period)
    if status=='zero' and count:raise ValueError('Zero month must contain no ledger entries')
    if status=='complete' and not count:raise ValueError('Empty month requires explicit zero approval')
    payload={'branch_id':branch,'month':period,'status':status,'reviewer':reviewer,'data_hash':digest,'approved_at':datetime.now(timezone.utc).isoformat()}
    signature=sign(key_from_env(),payload)
    with conn:conn.execute('INSERT OR REPLACE INTO data_period_reviews VALUES(?,?,?,?,?,?,?)',(branch,period,status,reviewer,digest,signature,payload['approved_at']))
    return {**payload,'row_count':count}

def verified_periods(conn,branch,periods):
    key=key_from_env();result=[]
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='data_period_reviews'").fetchone():raise ValueError('Period reviews required')
    for period in periods:
        row=conn.execute('SELECT * FROM data_period_reviews WHERE branch_id=? AND month=?',(branch,period)).fetchone()
        if not row:raise ValueError('Unreviewed or missing period: '+period)
        values=dict(row);signature=values.pop('signature');verify(key,values,signature)
        digest,count=period_hash(conn,branch,period)
        if digest!=values['data_hash']:raise IntegrityError('Data changed since review: '+period)
        if (values['status']=='zero' and count) or (values['status']=='complete' and not count):raise IntegrityError('Period review inconsistent with ledger')
        result.append(values)
    return result
