"""Export double-entry ledger into separate, currency-labelled Gold tables."""
import argparse
import json
import uuid
from pathlib import Path
from contextlib import closing
import pandas as pd
from backend.erp.service import ERP
from backend.erp.audit import verify_ledger


def export(erp,output):
    folder=Path(output)/uuid.uuid4().hex;folder.mkdir(parents=True)
    with closing(erp.connect()) as c:
        c.execute('BEGIN')
        integrity=verify_ledger(c,erp.audit_key)
        journal=pd.read_sql_query('''SELECT l.id line_id,d.id document_id,d.business_date,d.branch_id,d.kind,
            l.account,l.debit debit_minor,l.credit credit_minor,d.actor
            FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id ORDER BY d.business_date,l.id''',c)
        accounts=pd.read_sql_query('SELECT * FROM erp_accounts ORDER BY code',c)
        branches=pd.read_sql_query('SELECT * FROM erp_branches ORDER BY id',c)
        months=pd.read_sql_query('''SELECT DISTINCT branch_id,substr(business_date,1,7) month
            FROM erp_documents ORDER BY month,branch_id''',c)
        monthly=pd.read_sql_query('''SELECT d.branch_id,substr(d.business_date,1,7) month,
            SUM(CASE WHEN l.account='4000' THEN l.credit-l.debit ELSE 0 END) revenue_minor,
            SUM(CASE WHEN l.account='5000' THEN l.debit-l.credit ELSE 0 END) food_minor,
            SUM(CASE WHEN l.account='5100' THEN l.debit-l.credit ELSE 0 END) labor_minor,
            SUM(CASE WHEN l.account='5200' THEN l.debit-l.credit ELSE 0 END) rent_minor,
            SUM(CASE WHEN l.account='5300' THEN l.debit-l.credit ELSE 0 END) other_minor,
            SUM(CASE WHEN l.account='5400' THEN l.debit-l.credit ELSE 0 END) depreciation_minor
            FROM erp_lines l JOIN erp_documents d ON d.id=l.document_id GROUP BY d.branch_id,substr(d.business_date,1,7)''',c)
        c.rollback()
    if int(journal['debit_minor'].sum())!=int(journal['credit_minor'].sum()):raise ValueError('Ledger does not balance')
    monthly=months.merge(monthly,how='left',on=['branch_id','month']).fillna(0)
    numeric=['revenue_minor','food_minor','labor_minor','rent_minor','other_minor','depreciation_minor']
    for col in numeric:monthly[col]=monthly[col].astype('int64')
    monthly['profit_before_interest_tax_minor']=monthly['revenue_minor']-monthly[numeric[1:]].sum(axis=1)
    for frame in (journal,monthly):
        frame['currency']=erp.currency;frame['jurisdiction']=erp.jurisdiction
    for name,frame in [('fact_journal',journal),('fact_monthly_pnl',monthly),('dim_accounts',accounts),('dim_branches',branches)]:
        frame.to_csv(folder/(name+'.csv'),index=False,encoding='utf-8-sig')
    (folder/'manifest.json').write_text(json.dumps({'source':'erp_double_entry_mvp','currency':erp.currency,
        'jurisdiction':erp.jurisdiction,'minor_digits':0 if erp.currency=='VND' else 2,
        'integrity':integrity,'journal_rows':len(journal),'balanced':True,'note':'Separate ERP Gold, not legacy VND analytics. No statutory tax certification.'},indent=2))
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default='backend/data/erp.sqlite3');p.add_argument('--currency',default='GBP');p.add_argument('--jurisdiction',default='GB');p.add_argument('--output',default='backend/data/erp_gold')
    a=p.parse_args();print(export(ERP(a.db,a.currency,a.jurisdiction),a.output))
