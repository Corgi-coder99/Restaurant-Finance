from contextlib import closing
import asyncio
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import api
from backend.analytics import connect,initialize,import_csv,monthly_report,forecast,ROOT
from backend.data_quality import review_period
from backend.forecasting import evaluate,predict
from backend.integrity import IntegrityError
from backend.erp.service import ERP,ERPError

KEY='unit-test-only-audit-secret-not-production-987654321'
class AssuranceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.patch=patch.dict(os.environ,{'BEP_AUDIT_KEY':KEY});self.patch.start()
  self.c=connect(self.root/'analytics.sqlite3');initialize(self.c)
  import_csv(self.c,ROOT/'data/sample_entries.csv')
 def tearDown(self):self.c.close();self.patch.stop();self.tmp.cleanup()
 def approve(self):
  for row in monthly_report(self.c,'q1'):review_period(self.c,'q1',row['month'],'complete','Test reviewer')
 def test_filter_before_aggregation_and_branch_totals(self):
  rows=monthly_report(self.c,'q1','2025-01-01','2025-01-31')
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['month'],'2025-01')
  self.assertEqual(monthly_report(self.c,branches=[]),[])
  self.assertTrue(all(x['branch_id']=='q1' for x in monthly_report(self.c,branches=['q1'])))
  self.assertEqual(monthly_report(self.c,'q1','2025-01-02','2025-01-31'),[])
  with self.assertRaises(ValueError):monthly_report(self.c,'q1','2025-12-01','2025-01-01')
  with self.assertRaises(ValueError):monthly_report(self.c,"q1' OR 1=1 --")
 def test_unreviewed_stale_or_changed_data_blocks_forecast(self):
  with self.assertRaises(ValueError):forecast(self.c,'q1',3,'2026-01-01')
  self.approve();result=forecast(self.c,'q1',3,'2026-01-01')
  self.assertEqual(result['reviewed_months'],24)
  with self.assertRaises(ValueError):forecast(self.c,'q1')
  self.c.execute("UPDATE entries SET amount_vnd=amount_vnd+1 WHERE branch_id='q1' AND recognized_date='2025-12-01'");self.c.commit()
  with self.assertRaises(IntegrityError):forecast(self.c,'q1',3,'2026-01-01')
 def test_explicit_zero_month_not_implicit_fill(self):
  self.approve();self.c.execute("DELETE FROM entries WHERE branch_id='q1' AND recognized_date='2025-05-01'");self.c.commit()
  with self.assertRaises(IntegrityError):forecast(self.c,'q1',3,'2026-01-01')
  review_period(self.c,'q1','2025-05','zero','Reviewed closure')
  result=forecast(self.c,'q1',3,'2026-01-01');self.assertEqual(len(result['forecast']),3)
 def test_holdout_does_not_change_model_selection(self):
  seasonal=[100,20,30,70,80,90,110,140,160,170,150,200]*3
  components={'revenue':seasonal,'food':[20]*36,'rent':[10]*36}
  a=evaluate(components,3)
  altered={**components,'revenue':seasonal[:-3]+[9999,9999,9999]}
  b=evaluate(altered,3)
  self.assertEqual(a['selection'],b['selection'])
  self.assertLess(max(a['selection_origins'])+3,a['holdout_origin']+1)
  self.assertNotEqual(a['holdout'],b['holdout'])
  self.assertEqual(a['selection']['revenue']['method'],'seasonal_12')
 def test_short_data_and_zero_wape_are_not_false_certainty(self):
  with self.assertRaises(ValueError):evaluate({'revenue':[100]*12,'food':[10]*12},3)
  result=evaluate({'revenue':[0]*24,'food':[0]*24},3)
  self.assertIsNone(result['holdout']['revenue']['wape_pct']);self.assertTrue(result['warnings'])
  self.assertEqual(predict([1,2,3],3,'mean_last_3'),[2,2,2])
 def test_financial_logic_always_reconciles_forecast(self):
  self.approve();result=forecast(self.c,'q1',3,'2026-01-01')
  for r in result['forecast']:
   self.assertEqual(r['operating_profit_vnd'],r['revenue_vnd']-sum(r[k] for k in ['food_vnd','labor_vnd','rent_vnd','other_vnd']))
 def test_tampered_master_data_and_stock_are_detected(self):
  erp=ERP(self.root/'erp.sqlite3');erp.post({'kind':'purchase','date':'2026-11-08','branch_id':'q1','item_id':'rice','quantity':1000,'net_minor':100,'payment':'credit'},'purchase')
  with closing(erp.connect()) as c, c:c.execute('UPDATE erp_stock SET value_minor=101')
  with self.assertRaises(IntegrityError):erp.report()
  with closing(erp.connect()) as c, c:c.execute('UPDATE erp_stock SET value_minor=100');c.execute('UPDATE erp_products SET price_minor=1')
  with self.assertRaises(IntegrityError):erp.post({'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':10},'capital')
 def test_balanced_but_edited_journal_is_detected(self):
  erp=ERP(self.root/'edit.sqlite3');erp.post({'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':1000},'one')
  with closing(erp.connect()) as c, c:
   c.execute('DROP TRIGGER erp_no_update_line')
   c.execute('UPDATE erp_lines SET debit=2000 WHERE debit=1000');c.execute('UPDATE erp_lines SET credit=2000 WHERE credit=1000')
  with self.assertRaises(IntegrityError):erp.report()
 def test_wrong_key_and_payload_role_spoofing_fail(self):
  erp=ERP(self.root/'key.sqlite3');erp.post({'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':1000},'one')
  wrong=ERP(self.root/'key.sqlite3',audit_key=b'x'*32)
  with self.assertRaises(IntegrityError):wrong.report()
  with self.assertRaises(ERPError):erp.post({'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':1,'role':'owner'},'spoof')
 def test_api_auth_branch_scope_expiry_and_request_guards(self):
  users={'scope-q1':{'name':'Scoped','role':'owner','branches':['q1']},'no-scope':{'name':'No scope','role':'owner'},
    'expired':{'name':'Expired','role':'owner','branches':['q1'],'expires_at':'2000-01-01T00:00:00Z'}}
  self.approve()
  old=api.DB;api.DB=self.root/'analytics.sqlite3'
  async def check():
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),base_url='http://test') as client:
    self.assertEqual((await client.get('/api/reports/monthly')).status_code,401)
    h={'Authorization':'Bearer scope-q1'}
    response=await client.get('/api/reports/monthly',headers=h)
    self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'no-store')
    self.assertEqual({x['branch_id'] for x in response.json()['rows']},{'q1'})
    self.assertEqual((await client.get('/api/erp/report?branch=td',headers=h)).status_code,403)
    self.assertEqual((await client.get('/api/reports/monthly?branch=td',headers=h)).status_code,403)
    self.assertEqual((await client.get('/api/reports/monthly',headers={'Authorization':'Bearer expired'})).status_code,401)
    self.assertEqual((await client.get('/api/reports/monthly',headers={'Authorization':'Bearer no-scope'})).json()['rows'],[])
    payload={'kind':'capital','date':'2026-11-08','branch_id':'td','amount_minor':100}
    self.assertEqual((await client.post('/api/erp/documents',headers={**h,'Idempotency-Key':'blocked'},json=payload)).status_code,403)
    self.assertEqual((await client.post('/api/erp/documents',headers={**h,'Origin':'https://evil.example'},json=payload)).status_code,403)
    self.assertEqual((await client.post('/api/erp/documents',headers={**h,'Content-Type':'application/json'},content='x'*70000)).status_code,413)
    self.assertEqual((await client.post('/api/erp/documents',headers={**h,'Content-Type':'application/json'},content='{"kind":"sale","kind":"capital"}')).status_code,400)
    self.assertEqual((await client.post('/api/erp/documents',headers={**h,'Content-Type':'application/json'},content='{"amount_minor":NaN}')).status_code,400)
    self.assertEqual((await client.get('/api/reports/monthly?start=2026-99-99',headers=h)).status_code,422)
  try:
   with patch.dict(os.environ,{'BEP_ERP_USERS':json.dumps(users)}):asyncio.run(check())
  finally:api.DB=old

if __name__=='__main__':unittest.main()

class ExtendedAssuranceTests(unittest.TestCase):
 def test_api_guard_rate_limit_and_chunked_body(self):
  from backend.http_security import SecurityGuard
  async def endpoint(scope,receive,send):
   await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
   await send({'type':'http.response.body','body':b'{}'})
  async def check():
   guard=SecurityGuard(endpoint,limit=2)
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=guard),base_url='http://test') as c:
    self.assertEqual((await c.get('/api/a')).status_code,200)
    self.assertEqual((await c.get('/api/a')).status_code,200)
    self.assertEqual((await c.get('/api/a')).status_code,429)
   async def chunks():
    yield b'x'*40000;yield b'x'*40000
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=SecurityGuard(endpoint)),base_url='http://test') as c:
    r=await c.post('/api/a',headers={'Content-Type':'application/json'},content=chunks())
    self.assertEqual(r.status_code,413)
  asyncio.run(check())
 def test_unsigned_legacy_requires_explicit_migration(self):
  from backend.erp.audit import seal_legacy
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BEP_AUDIT_KEY':KEY}):
   erp=ERP(Path(tmp)/'old.sqlite3');erp.post({'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':100},'one')
   with closing(erp.connect()) as c, c:
    c.execute('DROP TRIGGER erp_no_delete_integrity');c.execute('DROP TRIGGER erp_no_delete_genesis')
    c.execute('DELETE FROM erp_integrity');c.execute('DELETE FROM erp_integrity_genesis')
   with self.assertRaises(IntegrityError):erp.report()
   with closing(erp.connect()) as c, c:
    c.execute('BEGIN IMMEDIATE');seal_legacy(c,erp.audit_key,'Reviewer','Reconciled to retained source documents')
   self.assertTrue(erp.report()['integrity']['verified'])
   with closing(erp.connect()) as c, c:
    with self.assertRaises(IntegrityError):seal_legacy(c,erp.audit_key,'Reviewer','Cannot reset')
 def test_erp_forecast_uses_closed_signed_periods_and_ledger_currency(self):
  from backend.erp.forecast import forecast_ledger
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BEP_AUDIT_KEY':KEY}):
   erp=ERP(Path(tmp)/'ledger.sqlite3')
   for i in range(24):
    year=2024+i//12;month=i%12+1;day=f'{year}-{month:02d}-28'
    erp.post({'kind':'expense','branch_id':'q1','date':day,'category':'rent','net_minor':100,'payment':'credit'},f'rent-{i}')
    if i==23:
     with self.assertRaises(ValueError):forecast_ledger(erp,'q1',3,'2026-01-01')
    erp.post({'kind':'close_period','branch_id':'q1','date':day},f'close-{i}')
   result=forecast_ledger(erp,'q1',3,'2026-01-01')
   self.assertEqual(result['currency'],'GBP');self.assertTrue(result['integrity']['verified'])
   self.assertEqual(result['forecast'][0]['profit_before_interest_tax_minor'],-100)
   self.assertEqual(result['forecast'][0]['month'],'2026-01')
