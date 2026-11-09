from contextlib import closing
import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import httpx
from backend.erp.service import ERP,ERPError
from backend.workspace.service import Workspace
from backend.integrity import IntegrityError
from backend.api import app

UTC=timezone.utc
class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'erp.sqlite3'
  self.env=patch.dict(os.environ,{'BEP_AUDIT_KEY':'unit-only-secret-not-for-production-123456789','BEP_ERP_DATABASE':str(self.path)});self.env.start()
  self.erp=ERP(self.path);self.now=datetime(2026,11,8,9,tzinfo=UTC);self.ops=Workspace(self.erp,lambda:self.now);self.n=0
  self.owner={'user_id':'owner','name':'Owner','role':'owner','branches':['q1','td']}
  self.manager={'user_id':'manager','name':'Manager','role':'manager','branches':['q1']}
  self.cash={'user_id':'cash','name':'Cashier','role':'cashier','employee_id':'e1','branches':['q1']}
  self.action(self.owner,'employee',{'employee_id':'e1','name':'Employee One','hourly_minor':1500})
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def action(self,who,kind,payload,branch='q1',key=None):
  self.n+=1;return self.ops.action(who,branch,kind,payload,key or 'action-'+str(self.n))
 def open(self,who=None):return self.ops.session(who or self.cash,'q1')['active_shift']
 def till(self,shift):return self.action(self.cash,'till_open',{'shift_id':shift['shift_id'],'opening_cash_minor':0})
 def stock(self):
  for item,qty,net in [('rice',10000,10000),('chicken',15000,30000)]:
   self.erp.post({'kind':'purchase','branch_id':'q1','date':'2026-11-08','item_id':item,'quantity':qty,'net_minor':net,'payment':'credit'},'buy-'+item)
 def sale(self,key='sale',activation=None):return self.ops.sale(self.cash,{'kind':'sale','branch_id':'q1','date':'2026-11-08','items':[{'product_id':'rice_chicken','quantity':1}],'tax_minor':0,'payment':'cash'},key,activation)
 def test_auto_open_refresh_does_not_duplicate_and_clock_only_ends_on_close(self):
  first=self.open();self.now+=timedelta(hours=3);second=self.open();self.assertEqual(first['shift_id'],second['shift_id'])
  self.assertEqual(len(self.ops.shift_summary(self.cash,'q1')['shifts']),1)
  self.now+=timedelta(hours=5)
  closed=self.action(self.cash,'shift_close',{'shift_id':first['shift_id'],'break_seconds':1800,'counted_cash_minor':0})
  self.assertEqual(closed['paid_seconds'],27000)
  self.assertEqual(sum(x['paid_seconds'] for x in self.ops.shift_summary(self.cash,'q1')['shifts'][0]['daily_hours']),27000)
 def test_cashier_cannot_manage_other_staff_or_other_branch(self):
  with self.assertRaises(PermissionError):self.action(self.cash,'employee',{'employee_id':'hack','name':'Hack','hourly_minor':999})
  with self.assertRaises(PermissionError):self.ops.management(self.manager,'td','2026-11')
  with self.assertRaises(PermissionError):self.ops.owner_summary(self.manager,'2026-11')
 def test_sale_requires_shift_and_cash_confirmation(self):
  self.stock()
  with self.assertRaises(ERPError):self.sale()
  shift=self.open()
  with self.assertRaises(ERPError):self.sale()
  self.till(shift);result=self.sale();self.assertEqual(result['status'],'posted')
  retry=self.sale();self.assertEqual(retry['status'],'already_posted')
  summary=self.ops.shift_summary(self.cash,'q1')['shifts'][0]
  self.assertEqual(summary['expected_cash_minor'],1200);self.assertEqual(len(summary['sales']),1)
 def test_discount_key_scoped_one_time_and_atomic_rollback(self):
  self.stock();shift=self.open();self.till(shift)
  self.action(self.manager,'campaign',{'campaign_id':'lunch','name':'Lunch','discount_bps':2000,'enabled':True,'starts_at':(self.now-timedelta(hours=1)).isoformat(),'ends_at':(self.now+timedelta(hours=2)).isoformat()})
  grant=self.action(self.manager,'grant',{'campaign_id':'lunch','employee_id':'e1'})
  result=self.sale('discount-sale',grant['activation_key']);receipt=self.ops.receipt(self.cash,result['document_id'])
  self.assertEqual(receipt['discount_minor'],240);self.assertEqual(receipt['net_minor'],960)
  with self.assertRaises(ERPError):self.sale('again',grant['activation_key'])
  self.assertEqual(self.sale('discount-sale',grant['activation_key'])['status'],'already_posted')
  self.assertEqual(self.erp.report()['pnl']['revenue_minor'],960)
 def test_expired_or_revoked_keys_rejected(self):
  self.stock();self.till(self.open())
  self.action(self.manager,'campaign',{'campaign_id':'promo','name':'Promo','discount_bps':1000,'enabled':True,'starts_at':(self.now-timedelta(hours=1)).isoformat(),'ends_at':(self.now+timedelta(hours=2)).isoformat()})
  grant=self.action(self.manager,'grant',{'campaign_id':'promo','employee_id':'e1','ttl_minutes':1});self.now+=timedelta(minutes=2)
  with self.assertRaises(ERPError):self.sale('expired',grant['activation_key'])
 def test_failed_stock_post_does_not_consume_promotion_and_cashier_cannot_read_costs(self):
  self.till(self.open())
  self.action(self.manager,'campaign',{'campaign_id':'p','name':'Promo','discount_bps':1000,'enabled':True,'starts_at':(self.now-timedelta(hours=1)).isoformat(),'ends_at':(self.now+timedelta(hours=2)).isoformat()})
  grant=self.action(self.manager,'grant',{'campaign_id':'p','employee_id':'e1'})
  with self.assertRaises(ERPError):self.sale('out-of-stock',grant['activation_key'])
  self.stock();result=self.sale('after-stock',grant['activation_key'])
  receipt=self.ops.receipt(self.cash,result['document_id']);self.assertNotIn('cost_minor',receipt)
  record=self.ops.shift_summary(self.cash,'q1')['shifts'][0]['sales'][0];self.assertNotIn('cost_minor',record)
  with self.assertRaises(PermissionError):self.ops.management(self.cash,'q1','2026-11')
 def test_revoked_and_wrong_employee_keys_fail_without_consuming_valid_key(self):
  self.stock();self.till(self.open())
  self.action(self.manager,'employee',{'employee_id':'e2','name':'Second','hourly_minor':1500})
  self.action(self.manager,'campaign',{'campaign_id':'p','name':'Promo','discount_bps':1000,'enabled':True,'starts_at':(self.now-timedelta(hours=1)).isoformat(),'ends_at':(self.now+timedelta(hours=2)).isoformat()})
  wrong=self.action(self.manager,'grant',{'campaign_id':'p','employee_id':'e2'})
  with self.assertRaises(ERPError):self.sale('wrong-staff',wrong['activation_key'])
  revoked=self.action(self.manager,'grant',{'campaign_id':'p','employee_id':'e1'})
  self.action(self.manager,'revoke_grant',{'grant_id':revoked['grant_id'],'reason':'Cancelled'})
  with self.assertRaises(ERPError):self.sale('revoked',revoked['activation_key'])
  self.assertEqual(self.erp.report()['pnl']['revenue_minor'],0)
 def test_handover_and_till_difference(self):
  self.stock();shift=self.open();self.till(shift);self.sale();self.now+=timedelta(hours=4)
  self.action(self.manager,'employee',{'employee_id':'e2','name':'Employee Two','hourly_minor':1600})
  close=self.action(self.cash,'shift_close',{'shift_id':shift['shift_id'],'counted_cash_minor':1190,'handover_to':'e2'})
  self.assertEqual(close['cash_difference_minor'],-10)
  other={**self.cash,'user_id':'cash2','employee_id':'e2'};next_shift=self.open(other)
  self.assertEqual(next_shift['opening_cash_minor'],1190);self.assertEqual(next_shift['handover_from'],shift['shift_id'])
 def test_dst_and_midnight_payroll_preserve_exact_time(self):
  self.now=datetime(2026,10,24,22,tzinfo=UTC);shift=self.open()
  self.now=datetime(2026,10,25,4,tzinfo=UTC);closed=self.action(self.cash,'shift_close',{'shift_id':shift['shift_id'],'counted_cash_minor':0,'break_seconds':1800})
  self.assertEqual(closed['paid_seconds'],19800)
  summary=self.ops.shift_summary(self.cash,'q1')['shifts'][0];parts=summary['daily_hours']
  self.assertEqual(len(parts),2);self.assertEqual(sum(x['paid_seconds'] for x in parts),19800)
 def test_payroll_needs_review_then_accrues_once_and_preserves_old_rate(self):
  shift=self.open();self.now+=timedelta(hours=8)
  self.action(self.cash,'shift_close',{'shift_id':shift['shift_id'],'counted_cash_minor':0})
  self.action(self.manager,'employee',{'employee_id':'e1','name':'Employee One','hourly_minor':2000,'inactive_from':'2026-11-09'})
  self.now=datetime(2026,12,1,1,tzinfo=UTC)
  with self.assertRaises(ERPError):self.ops.accrue_payroll(self.manager,'q1','2026-11','2026-11-30','payroll')
  self.action(self.manager,'shift_review',{'shift_id':shift['shift_id'],'reason':'Hours checked'})
  result=self.ops.accrue_payroll(self.manager,'q1','2026-11','2026-11-30','payroll')
  self.assertEqual(result['status'],'posted');self.assertEqual(self.erp.report()['pnl']['labor_minor'],12000)
  self.assertEqual(self.erp.report()['liabilities_breakdown']['payroll_payable_minor'],12000)
  self.assertEqual(self.ops.accrue_payroll(self.manager,'q1','2026-11','2026-11-30','payroll')['status'],'already_posted')
  with self.assertRaises(ERPError):self.open()
 def test_workspace_tampering_blocks_use(self):
  self.open()
  with closing(self.erp.connect()) as c, c:
   c.execute('DROP TRIGGER workspace_no_update');c.execute("UPDATE workspace_events SET payload='{}' WHERE kind='employee'")
  with self.assertRaises(IntegrityError):self.ops.session(self.cash,'q1',False)
 def test_api_enforces_portal_roles(self):
  users={'employee':self.cash,'manager':self.manager,'owner':self.owner}
  async def check():
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
    h={'Authorization':'Bearer employee'}
    self.assertEqual((await c.get('/api/workspace/owner?month=2026-11',headers=h)).status_code,403)
    self.assertEqual((await c.get('/api/workspace/management?month=2026-11&branch=q1',headers=h)).status_code,403)
    self.assertEqual((await c.post('/api/workspace/session/open',headers=h,json={'branch_id':'q1'})).status_code,200)
    self.assertEqual((await c.get('/api/workspace/session?branch=td',headers=h)).status_code,403)
  with patch.dict(os.environ,{'BEP_ERP_USERS':json.dumps(users)}):asyncio.run(check())

if __name__=='__main__':unittest.main()
