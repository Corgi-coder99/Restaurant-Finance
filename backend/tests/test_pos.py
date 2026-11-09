import json,os,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from backend.erp.service import ERP,ERPError
from backend.workspace.service import Workspace
from backend.workspace.pos import quote

class PosTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'BEP_AUDIT_KEY':'test-pos-key-not-for-production-123456789'});self.env.start()
  self.erp=ERP(Path(self.tmp.name)/'pos.sqlite3');self.ops=Workspace(self.erp,lambda:datetime(2026,11,9,10,tzinfo=timezone.utc));self.n=0
  self.owner={'user_id':'o','name':'Owner','role':'owner','branches':['q1']};self.cash={'user_id':'c','name':'Cashier','role':'cashier','branches':['q1'],'employee_id':'e1'}
  self.act('employee',{'employee_id':'e1','name':'Staff','hourly_minor':1500})
  self.product={'id':'rice_chicken','name':'Chicken rice','names':{'vi':'Cơm gà','en':'Chicken rice','fr':'Riz au poulet','de':'Hähnchen mit Reis'},'price_minor':1200,'vat_bps':2000,'category':'main','icon':'rice','active':True,'recipe':[{'item_id':'rice','quantity':100},{'item_id':'chicken','quantity':150}],'components':[]}
  self.act('menu',self.product);self.act('table',{'id':'T1','label':'T1','seats':4,'x':10,'y':10})
  for id,qty in [('rice',10000),('chicken',15000)]:self.erp.post({'kind':'purchase','branch_id':'q1','date':'2026-11-09','item_id':id,'quantity':qty,'net_minor':10000,'payment':'credit'},'buy-'+id)
  s=self.ops.session(self.cash,'q1')['active_shift'];self.act('till_open',{'shift_id':s['shift_id'],'opening_cash_minor':0},self.cash)
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def act(self,kind,p,who=None):self.n+=1;return self.ops.action(who or self.owner,'q1',kind,p,'a'+str(self.n))
 def sale(self,key='s',**kwargs):return self.ops.sale(self.cash,{'kind':'sale','branch_id':'q1','date':'2026-11-09','items':[{'product_id':'rice_chicken','quantity':1}],'tax_minor':999999,'payment':'cash'},key,**kwargs)
 def test_server_prices_vat_and_receipt_immutable_after_menu_edit(self):
  result=self.sale(expected_gross_minor=1200);receipt=self.ops.receipt(self.cash,result['document_id'])
  self.assertEqual((receipt['net_minor'],receipt['tax_minor'],receipt['gross_minor']),(1000,200,1200))
  self.act('menu',{**self.product,'price_minor':1800,'name':'Updated'})
  self.assertEqual(self.ops.receipt(self.cash,result['document_id']),receipt)
  with self.assertRaises(ERPError):self.sale('changed',expected_gross_minor=1200)
  self.assertEqual(self.erp.report()['pnl']['revenue_minor'],1000)
 def test_table_revision_payment_atomicity_and_replay(self):
  items=[{'product_id':'rice_chicken','quantity':1}]
  order=self.act('order_save',{'table_id':'T1','items':items,'revision':0},self.cash)
  with self.assertRaises(ERPError):self.act('order_save',{'table_id':'T1','items':items,'revision':0},self.cash)
  result=self.sale(order_id=order['order_id'],order_revision=1,expected_gross_minor=1200)
  self.assertEqual(self.ops.receipt(self.cash,result['document_id'])['table_id'],'T1')
  with self.assertRaises(ERPError):self.sale('double',order_id=order['order_id'],order_revision=1)
  self.assertEqual(self.sale(order_id=order['order_id'],order_revision=1,expected_gross_minor=1200)['status'],'already_posted')
  self.assertEqual(self.ops.session(self.cash,'q1',False)['orders'],[])
 def test_combo_consumes_component_recipe_and_cashier_cannot_change_price(self):
  self.act('menu',{**self.product,'id':'duo','name':'Duo','price_minor':2000,'category':'combo','icon':'combo','recipe':[],'components':[{'product_id':'rice_chicken','quantity':2}]})
  result=self.ops.sale(self.cash,{'kind':'sale','branch_id':'q1','date':'2026-11-09','items':[{'product_id':'duo','quantity':1}],'payment':'cash','tax_minor':0},'duo')
  self.assertEqual(self.ops.receipt(self.cash,result['document_id'])['gross_minor'],2000)
  stock={x['item_id']:x['quantity'] for x in self.erp.report()['stock']};self.assertEqual(stock['rice'],9800);self.assertEqual(stock['chicken'],14700)
  with self.assertRaises(PermissionError):self.act('menu',{**self.product,'price_minor':1},self.cash)
 def test_disabled_combo_does_not_block_unrelated_sales(self):
  self.act('menu',{**self.product,'id':'other','active':False})
  self.act('menu',{**self.product,'id':'duo','recipe':[],'components':[{'product_id':'other','quantity':1}]})
  self.assertEqual(self.sale()['status'],'posted')
 def test_quote_key_is_read_only_and_checkout_revalidates_total(self):
  self.act('campaign',{'campaign_id':'p','name':'Offer','discount_bps':2000,'enabled':True,'starts_at':'2026-11-09T09:00:00+00:00','ends_at':'2026-11-09T12:00:00+00:00'})
  grant=self.act('grant',{'campaign_id':'p','employee_id':'e1'})
  q=self.ops.quote_order(self.cash,'q1',[{'product_id':'rice_chicken','quantity':1}],grant['activation_key']);self.assertEqual(q['gross_minor'],960)
  self.assertEqual(self.ops.quote_order(self.cash,'q1',[{'product_id':'rice_chicken','quantity':1}],grant['activation_key']),q)
  result=self.sale(activation_key=grant['activation_key'],expected_gross_minor=960);self.assertEqual(self.ops.receipt(self.cash,result['document_id'])['tax_minor'],160)
  with self.assertRaises(ERPError):self.ops.quote_order(self.cash,'q1',[{'product_id':'rice_chicken','quantity':1}],grant['activation_key'])
 def test_mixed_vat_discount_exact_reconciliation(self):
  menu={id:{**self.product,'id':id,'price_minor':p,'vat_bps':v} for id,p,v in [('a',999,2000),('b',501,550),('c',300,0)]}
  q=quote(menu,[{'product_id':id,'quantity':3} for id in menu],1750)
  self.assertEqual(q['gross_minor'],q['net_minor']+q['tax_minor']);self.assertEqual(q['discount_minor'],sum(x['discount_minor'] for x in q['sale_lines']))
  self.assertEqual(q['gross_minor'],q['subtotal_minor']-q['discount_minor'])
  for l in q['sale_lines']:self.assertEqual(l['net_minor']+l['tax_minor'],l['gross_minor'])
