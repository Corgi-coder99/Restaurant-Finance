from contextlib import closing
import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend.erp.service import ERP,ERPError
from backend.erp.demo import scenario
from backend.api import app

class ERPTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'BEP_AUDIT_KEY':'test-audit-key-not-for-production-0123456789'});self.env.start()
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'erp.sqlite3';self.erp=ERP(self.path,'GBP','GB');self.counter=0
 def tearDown(self):self.tmp.cleanup();self.env.stop()
 def post(self,kind,**values):
  self.counter+=1
  return self.erp.post({'kind':kind,'branch_id':'q1','date':'2026-11-08',**values},str(self.counter))
 def test_whole_workflow_reconciles_cash_assets_and_profit(self):
  result=scenario(self.erp);r=result['steps'][-1]['report']
  self.assertTrue(r['balanced']);self.assertEqual(r['pnl']['profit_before_interest_tax_minor'],3500)
  self.assertEqual(r['liquidity']['bank_minor'],382000)
  self.assertEqual(r['liquidity']['cash_minor'],13200)
  self.assertEqual(r['liquidity']['liquidity_after_reserve_minor'],375200)
  self.assertEqual(sum(x['value_minor'] for x in r['stock']),36000)
  self.assertEqual(r['assets'][0]['net_book_minor'],57500)
  self.assertEqual(sum(x['remaining_minor'] for x in r['documents']),0)
  # Buying chairs does not immediately deduct their full cost from profit.
  self.assertEqual(result['steps'][6]['report']['pnl']['profit_before_interest_tax_minor'],result['steps'][7]['report']['pnl']['profit_before_interest_tax_minor'])
  # Reserve target has no accounting expense or cash outflow.
  self.assertEqual(result['steps'][-2]['report']['pnl'],r['pnl'])
  for step in result['steps']:
   for doc in step['report']['documents']:
    self.assertEqual(sum(x['debit'] for x in doc['lines']),sum(x['credit'] for x in doc['lines']))
 def test_retry_never_duplicates_stock(self):
  p={'kind':'purchase','date':'2026-11-08','branch_id':'q1','item_id':'rice','quantity':1000,'net_minor':100,'payment':'credit'}
  first=self.erp.post(p,'same');second=self.erp.post(p,'same')
  self.assertEqual(first['document_id'],second['document_id']);self.assertEqual(second['status'],'already_posted')
  self.assertEqual(self.erp.report()['stock'][0]['quantity'],1000)
  with self.assertRaises(ERPError):self.erp.post({**p,'net_minor':200},'same')
 def test_insufficient_stock_rolls_back_partial_consumption(self):
  self.post('purchase',item_id='rice',quantity=1000,net_minor=100,payment='credit')
  with self.assertRaises(ERPError):self.post('sale',items=[{'product_id':'rice_chicken','quantity':1}])
  r=self.erp.report();self.assertEqual(r['stock'][0]['quantity'],1000);self.assertEqual(len(r['documents']),1)
 def test_credit_sale_and_partial_collection(self):
  self.post('purchase',item_id='rice',quantity=1000,net_minor=100,payment='credit')
  self.post('purchase',item_id='chicken',quantity=1500,net_minor=300,payment='credit')
  sale=self.post('sale',items=[{'product_id':'rice_chicken','quantity':1}],payment='credit',tax_minor=120)
  self.post('collect',invoice_id=sale['document_id'],amount_minor=500,payment='cash')
  with self.assertRaises(ERPError):self.post('collect',invoice_id=sale['document_id'],amount_minor=821)
  r=self.erp.report();row=next(x for x in r['documents'] if x['id']==sale['document_id']);self.assertEqual(row['remaining_minor'],820)
 def test_no_cash_overdraft_and_no_supplier_overpayment(self):
  with self.assertRaises(ERPError):self.post('expense',net_minor=100,category='rent',payment='bank')
  purchase=self.post('purchase',item_id='rice',quantity=1000,net_minor=100,payment='credit')
  self.post('capital',amount_minor=1000)
  with self.assertRaises(ERPError):self.post('pay',invoice_id=purchase['document_id'],amount_minor=101)
  self.assertEqual(len(self.erp.report()['documents']),2)
 def test_period_close_role_and_immutability(self):
  capital=self.post('capital',amount_minor=10000)
  p={'kind':'expense','date':'2026-11-08','branch_id':'q1','category':'rent','net_minor':10,'payment':'credit'}
  with self.assertRaises(PermissionError):self.erp.post(p,'cashier',role='cashier')
  self.post('close_period')
  with self.assertRaises(ERPError):self.post('expense',category='rent',net_minor=10,payment='credit')
  with closing(self.erp.connect()) as conn, conn:
   with self.assertRaises(sqlite3.IntegrityError):conn.execute('UPDATE erp_lines SET debit=1 WHERE document_id=?',(capital['document_id'],))
 def test_depreciation_unique_month_and_currency_isolation(self):
  self.post('capital',amount_minor=10000)
  asset=self.post('asset',name='Bàn',net_minor=2400,life_months=24)
  self.post('depreciate',asset_id=asset['document_id'])
  with self.assertRaises(ERPError):self.post('depreciate',asset_id=asset['document_id'])
  with self.assertRaises(ERPError):ERP(self.path,'EUR','FR')
  euro=ERP(Path(self.tmp.name)/'fr.sqlite3','EUR','FR');self.assertEqual(euro.report()['currency'],'EUR')
 def test_expense_reversal_and_asof(self):
  exp=self.post('expense',category='rent',net_minor=1000,payment='credit')
  self.assertEqual(self.erp.report()['pnl']['rent_minor'],1000)
  self.post('reverse_expense',document_id=exp['document_id'])
  self.assertEqual(self.erp.report()['pnl']['rent_minor'],0)
  self.assertEqual(self.erp.report()['documents'][0]['remaining_minor'],0)
  self.assertEqual(self.erp.report(end='2026-11-07')['documents'],[])
 def test_depreciation_rounding_reconciles_exactly(self):
  self.post('capital',amount_minor=10000)
  asset=self.post('asset',name='Equipment',net_minor=1000,life_months=24)
  for index in range(24):
   absolute=2026*12+10+index
   day=f'{absolute//12:04d}-{absolute%12+1:02d}-08'
   self.erp.post({'kind':'depreciate','branch_id':'q1','date':day,'asset_id':asset['document_id']},f'dep-{index}')
  r=self.erp.report()
  self.assertEqual(r['assets'][0]['depreciated_minor'],1000)
  self.assertEqual(r['assets'][0]['net_book_minor'],0)
  self.assertTrue(r['balanced'])

 def test_authenticated_api_and_authorization(self):
  env={'BEP_ERP_USERS':json.dumps({'test-owner':{'name':'Owner','role':'owner','branches':['q1']},'test-cashier':{'name':'Cashier','role':'cashier','branches':['q1']}}),'BEP_ERP_DATABASE':str(self.path),'BEP_ERP_CURRENCY':'GBP','BEP_ERP_JURISDICTION':'GB'}
  async def check():
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
    self.assertEqual((await c.get('/api/erp/report')).status_code,401)
    self.assertEqual((await c.get('/api/erp/report',headers={'Authorization':'Bearer test-cashier'})).status_code,403)
    headers={'Authorization':'Bearer test-owner','Idempotency-Key':'api-capital'}
    p={'kind':'capital','date':'2026-11-08','branch_id':'q1','amount_minor':10000}
    self.assertEqual((await c.post('/api/erp/documents',headers=headers,json=p)).status_code,200)
    self.assertEqual((await c.post('/api/erp/documents',headers=headers,json=p)).json()['status'],'already_posted')
    self.assertEqual((await c.get('/api/erp/report',headers=headers)).json()['liquidity']['bank_minor'],10000)
  with patch.dict(os.environ,env):asyncio.run(check())

if __name__=='__main__':unittest.main()
