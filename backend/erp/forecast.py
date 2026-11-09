"""Forecast from signed, closed ERP periods, in the ledger's own minor units."""
from datetime import date
from contextlib import closing
import pandas as pd
from backend.erp.audit import verify_ledger
from backend.forecasting import evaluate

def forecast_ledger(erp,branch,horizon=3,as_of=None):
    cutoff=date.today() if as_of is None else date.fromisoformat(as_of)
    if as_of is not None and cutoff.isoformat()!=as_of:raise ValueError('Use ISO YYYY-MM-DD cutoff')
    if cutoff>date.today():raise ValueError('Future cutoff not allowed')
    current=pd.Period(cutoff,freq='M');last=current-1
    with closing(erp.connect()) as c:
        c.execute('BEGIN');integrity=verify_ledger(c,erp.audit_key)
        if not c.execute('SELECT 1 FROM erp_branches WHERE id=?',(branch,)).fetchone():raise ValueError('Unknown branch')
        first=c.execute("SELECT MIN(substr(business_date,1,7)) FROM erp_documents WHERE branch_id=? AND business_date<?",(branch,str(current)+'-01')).fetchone()[0]
        if not first:raise ValueError('No completed history')
        periods=[str(p) for p in pd.period_range(first,last,freq='M')]
        closed={r[0] for r in c.execute('SELECT month FROM erp_periods WHERE branch_id=?',(branch,))}
        if set(periods)-closed:raise ValueError('All history months through the last completed month must be closed before forecasting')
        components={'revenue_minor':'4000','food_minor':'5000','labor_minor':'5100','rent_minor':'5200','other_minor':'5300','depreciation_minor':'5400'}
        balances={(row[0],row[1]):row[2] for row in c.execute('SELECT substr(d.business_date,1,7),l.account,SUM(l.debit-l.credit) FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id WHERE d.branch_id=? AND d.business_date<? GROUP BY substr(d.business_date,1,7),l.account',(branch,str(current)+'-01'))}
        series={key:[(-1 if key=='revenue_minor' else 1)*balances.get((month,account),0) for month in periods] for key,account in components.items()}
        result=evaluate(series,horizon)
    output=[]
    for i in range(horizon):
        amounts={key:result['future'][key][i] for key in components}
        output.append({'month':str(last+i+1),**amounts,'profit_before_interest_tax_minor':amounts['revenue_minor']-sum(amounts[k] for k in components if k!='revenue_minor')})
    return {'currency':erp.currency,'jurisdiction':erp.jurisdiction,'branch_id':branch,'as_of':cutoff.isoformat(),
        'integrity':integrity,'status':'review_required' if result['warnings'] else 'validated_baseline','forecast':output,
        'model_selection':result['selection'],'holdout':result['holdout'],'profit_holdout':result['profit_holdout'],
        'warnings':result['warnings'],'limitations':[result['validation_note'],result['uncertainty_note']]}
