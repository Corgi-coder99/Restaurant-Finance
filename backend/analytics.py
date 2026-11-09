"""SQL ledger aggregation + pandas/NumPy analysis. Currency: integer VND."""
import csv
import sqlite3
from datetime import date
from pathlib import Path
from backend.data_quality import REVIEW_SCHEMA,verified_periods
from backend.forecasting import evaluate
import pandas as pd

ROOT = Path(__file__).parent
CATEGORIES = {'revenue', 'food', 'labor', 'rent', 'other'}

def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def initialize(conn):
    conn.executescript((ROOT / 'sql/schema.sql').read_text())
    conn.execute(REVIEW_SCHEMA)
    with conn:
        conn.executemany('INSERT OR IGNORE INTO branches VALUES (?,?,?)', [
            ('q1', 'Bếp Quận 1', 'VND'), ('td', 'Bếp Thảo Điền', 'VND'),
            ('dn', 'Bếp Đà Nẵng', 'VND')])

def import_csv(conn, path):
    """Validate entire file first; atomic import. Duplicate documents reject batch."""
    rows = []
    known = {r['id'] for r in conn.execute('SELECT id FROM branches')}
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'branch_id','document_id','line_number','recognized_date','category','amount_vnd','source'}
        if not reader.fieldnames or len(reader.fieldnames)!=len(required) or set(reader.fieldnames) != required:
            raise ValueError('CSV columns must be: ' + ','.join(sorted(required)))
        for number, r in enumerate(reader, 2):
            try:
                if r['branch_id'] not in known or r['category'] not in CATEGORIES:
                    raise ValueError('Unknown branch/category')
                if None in r or any(v is None for v in r.values()):raise ValueError('CSV row column count mismatch')
                if not r['document_id'].strip() or not r['source'].strip():
                    raise ValueError('Missing document/source')
                if date.fromisoformat(r['recognized_date']).isoformat() != r['recognized_date']:
                    raise ValueError('Use YYYY-MM-DD')
                amount, line = int(r['amount_vnd']), int(r['line_number'])
                if amount <= 0 or line <= 0 or amount > 9_000_000_000_000:
                    raise ValueError('Invalid amount/line number')
                rows.append((r['branch_id'],r['document_id'].strip(),line,r['recognized_date'],r['category'],amount,r['source'].strip()))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'CSV row {number}: {exc}') from exc
    try:
        with conn:
            conn.executemany('INSERT INTO entries(branch_id,document_id,line_number,recognized_date,category,amount_vnd,source) VALUES (?,?,?,?,?,?,?)', rows)
    except sqlite3.IntegrityError as exc:
        raise ValueError('Import rejected: duplicate document line or invalid data; no rows imported') from exc
    return len(rows)

def monthly_report(conn, branch=None, start=None, end=None, branches=None):
    """Filter raw recognised entries before aggregation. All values are parameters."""
    known={row['id'] for row in conn.execute('SELECT id FROM branches')}
    if branch is not None and branch not in known:raise ValueError('Unknown branch')
    if branches is not None and any(b not in known for b in branches):raise ValueError('Unknown branch in scope')
    for value in (start,end):
        if value is not None and (not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value):raise ValueError('Use ISO YYYY-MM-DD dates')
    if start and end and start>end:raise ValueError('Start date must precede end date')
    clauses=[];params=[]
    if branch is not None:clauses.append('branch_id=?');params.append(branch)
    if branches is not None:
        if not branches:return []
        clauses.append('branch_id IN ('+','.join('?' for _ in branches)+')');params.extend(branches)
    if start:clauses.append('recognized_date>=?');params.append(start)
    if end:clauses.append('recognized_date<=?');params.append(end)
    cols=['revenue','food','labor','rent','other']
    select=['branch_id',"substr(recognized_date,1,7) AS month"]
    select.extend("SUM(CASE WHEN category='"+name+"' THEN amount_vnd ELSE 0 END) AS "+name+'_vnd' for name in cols)
    query='SELECT '+','.join(select)+' FROM entries'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' GROUP BY branch_id,substr(recognized_date,1,7) ORDER BY month,branch_id'
    rows=[]
    for record in conn.execute(query,params):
        r=dict(record);cost=sum(r[k+'_vnd'] for k in cols[1:]);profit=r['revenue_vnd']-cost
        if cost>2**63-1:raise ValueError('Aggregated cost exceeds supported monetary range')
        r.update(total_cost_vnd=cost,operating_profit_vnd=profit,
            operating_margin_pct=profit/r['revenue_vnd']*100 if r['revenue_vnd'] else None,
            rent_to_revenue_pct=r['rent_vnd']/r['revenue_vnd']*100 if r['revenue_vnd'] else None)
        rows.append(r)
    return rows

def forecast(conn,branch,horizon=3,as_of=None):
    if type(horizon) is not int or not 1<=horizon<=6:raise ValueError('horizon must be 1..6')
    cutoff=date.today() if as_of is None else date.fromisoformat(as_of)
    if as_of is not None and cutoff.isoformat()!=as_of:raise ValueError('Use ISO YYYY-MM-DD as_of date')
    if cutoff>date.today():raise ValueError('Forecast cutoff cannot be in the future')
    rows=monthly_report(conn,branch)
    current=pd.Period(cutoff,freq='M');last=current-1
    history={row['month']:row for row in rows if pd.Period(row['month'],freq='M')<current}
    if not history:raise ValueError('No completed history')
    first=min(history);periods=[str(p) for p in pd.period_range(first,last,freq='M')]
    if max(history)!=str(last):
        # Only a deliberately reviewed zero month can fill the most recent gap.
        gap=[str(p) for p in pd.period_range(pd.Period(max(history),freq='M')+1,last,freq='M')]
        verified_periods(conn,branch,gap)
    approvals=verified_periods(conn,branch,periods)
    cols=['revenue_vnd','food_vnd','labor_vnd','rent_vnd','other_vnd']
    values={key:[int(history[period][key]) if period in history else 0 for period in periods] for key in cols}
    result=evaluate(values,horizon);output=[]
    for index in range(horizon):
        amounts={key:result['future'][key][index] for key in cols}
        output.append({'month':str(last+index+1),**amounts,
            'operating_profit_vnd':amounts['revenue_vnd']-sum(amounts[k] for k in cols[1:])})
    start_index=result['holdout_origin']
    return {'method':'validated_component_selection','currency':'VND','status':'review_required' if result['warnings'] else 'validated_baseline',
        'as_of':cutoff.isoformat(),'history_end':str(last),'forecast':output,
        'model_selection':result['selection'],
        'backtest':{'test_months':horizon,'months':periods[start_index:],
            'revenue_mae_vnd':result['holdout']['revenue_vnd']['mae'],
            'revenue_wape_pct':result['holdout']['revenue_vnd']['wape_pct'],
            'profit_mae_vnd':result['profit_holdout']['mae']},
        'reviewed_months':len(approvals),'warnings':result['warnings'],
        'limitations':[result['validation_note'],result['uncertainty_note'],
            'Only three baseline models compared. Future accuracy is not guaranteed.',
            'Completeness approval is a human assertion, not automatic proof of genuine invoices.']}
