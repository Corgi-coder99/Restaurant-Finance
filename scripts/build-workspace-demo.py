"""Publish only synthetic role previews; no live credentials or promotion key."""
import json,secrets,tempfile,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from backend.erp.service import ERP
from backend.workspace.service import Workspace
UTC=timezone.utc
with tempfile.TemporaryDirectory() as tmp:
 currency=os.environ.get('DEMO_CURRENCY','GBP');erp=ERP(Path(tmp)/'demo.sqlite3',currency=currency,jurisdiction='FR' if currency=='EUR' else 'GB',audit_key=secrets.token_bytes(32));now=[datetime(2026,11,8,9,tzinfo=UTC)];ops=Workspace(erp,lambda:now[0]);counter=[0]
 owner={'user_id':'owner-demo','name':'Chủ nhà hàng','role':'owner','branches':['q1','td','dn']}
 manager={'user_id':'manager-demo','name':'Quản lý cơ sở','role':'manager','branches':['q1']}
 staff={'user_id':'cashier-demo','name':'Minh Anh','role':'cashier','employee_id':'e1','branches':['q1']}
 staff2={**staff,'user_id':'cashier-2-demo','name':'Hoàng Nam','employee_id':'e2'}
 def act(who,kind,p):
  counter[0]+=1;return ops.action(who,'q1',kind,p,'demo-'+str(counter[0]))
 def post(kind,**p):
  counter[0]+=1;return erp.post({'kind':kind,'branch_id':'q1','date':'2026-11-08',**p},'doc-'+str(counter[0]))
 for b in ['q1','td','dn']:
  counter[0]+=1;ops.action(owner,b,'settings',{'timezone':'Europe/Paris' if currency=='EUR' else 'Europe/London'},'zone-'+b)
 act(manager,'receipt_profile',{'merchant_name':'Bếp Bistro · DEMO','address':'Paris · France' if currency=='EUR' else 'London · United Kingdom','vat_number':'DEMO'})
 menu=[
  ('rice_chicken',{'vi':'Cơm gà','en':'Chicken rice','fr':'Riz au poulet','de':'Hähnchen mit Reis'},1200,'main','rice',[{'item_id':'rice','quantity':100},{'item_id':'chicken','quantity':150}],[]),
  ('grilled_chicken',{'vi':'Gà nướng','en':'Grilled chicken','fr':'Poulet grillé','de':'Gegrilltes Hähnchen'},1600,'main','chicken',[{'item_id':'chicken','quantity':200}],[]),
  ('sparkling_water',{'vi':'Nước có ga','en':'Sparkling water','fr':'Eau pétillante','de':'Mineralwasser'},350,'drink','drink',[],[]),
  ('rice_duo',{'vi':'Combo cơm gà & nước','en':'Chicken rice & water','fr':'Menu riz au poulet et eau','de':'Hähnchen-Reis-Menü mit Wasser'},1450,'combo','combo',[],[{'product_id':'rice_chicken','quantity':1},{'product_id':'sparkling_water','quantity':1}])]
 # Independent sample pricing; EUR amounts are not converted from GBP live.
 for id,names,price,cat,icon,recipe,components in menu:
  act(manager,'menu',{'id':id,'name':names['en'],'names':names,'price_minor':price+(100 if currency=='EUR' and cat!='drink' else 0),'vat_bps':2000,'category':cat,'icon':icon,'active':True,'recipe':recipe,'components':components})
 for i,(x,y) in enumerate([(9,10),(39,10),(69,10),(9,59),(39,59),(69,59)],1):
  act(manager,'table',{'id':'T'+str(i),'label':'T'+str(i),'seats':4 if i<5 else 2,'x':x,'y':y})
 post('capital',amount_minor=500000)
 for item,qty,net in [('rice',20000,20000),('chicken',30000,60000)]:
  doc=post('purchase',item_id=item,quantity=qty,net_minor=net,payment='credit');post('pay',invoice_id=doc['document_id'],amount_minor=net,payment='bank')
 act(manager,'employee',{'employee_id':'e1','name':'Minh Anh','hourly_minor':1500})
 act(manager,'employee',{'employee_id':'e2','name':'Hoàng Nam','hourly_minor':1600})
 for item in ['rice','chicken']:act(manager,'reorder',{'item_id':item,'minimum':15000,'daily_target':20000,'weekly_target':50000})
 shift=ops.session(staff,'q1')['active_shift'];act(staff,'till_open',{'shift_id':shift['shift_id'],'opening_cash_minor':0})
 act(manager,'campaign',{'campaign_id':'lunch','name':'Ưu đãi bữa trưa','discount_bps':2000,'enabled':True,'starts_at':now[0].isoformat(),'ends_at':(now[0]+timedelta(hours=8)).isoformat()})
 grant=act(manager,'grant',{'campaign_id':'lunch','employee_id':'e1'})
 result=ops.sale(staff,{'kind':'sale','branch_id':'q1','date':'2026-11-08','items':[{'product_id':'rice_chicken','quantity':100}],'payment':'cash','tax_minor':0},'sale-1',grant['activation_key'])
 now[0]+=timedelta(hours=3)
 cashier={'session':ops.session(staff,'q1',False),'summary':ops.shift_summary(staff,'q1'),'receipt':ops.receipt(staff,result['document_id'])}
 now[0]=datetime(2026,11,8,17,tzinfo=UTC)
 act(staff,'shift_close',{'shift_id':shift['shift_id'],'break_seconds':1800,'counted_cash_minor':(103900 if currency=='EUR' else 95900),'handover_to':'e2','note':'Chênh lệch tiền mặt £1 cần đối soát.'})
 second=ops.session(staff2,'q1')['active_shift'];act(staff2,'till_open',{'shift_id':second['shift_id'],'opening_cash_minor':(103900 if currency=='EUR' else 95900)})
 now[0]+=timedelta(hours=1)
 ops.sale(staff2,{'kind':'sale','branch_id':'q1','date':'2026-11-08','items':[{'product_id':'rice_chicken','quantity':20}],'payment':'cash','tax_minor':0},'sale-2')
 now[0]=datetime(2026,11,8,23,tzinfo=UTC);act(staff2,'shift_close',{'shift_id':second['shift_id'],'counted_cash_minor':(129900 if currency=='EUR' else 119900)})
 post('expense',category='rent',net_minor=10000,payment='bank');post('expense',category='other',net_minor=3000,payment='bank')
 now[0]=datetime(2026,11,9,10,tzinfo=UTC)
 for s in [shift,second]:act(manager,'shift_review',{'shift_id':s['shift_id'],'reason':'Đã đối chiếu giờ công và bàn giao'})
 act(manager,'employee',{'employee_id':'e1','name':'Minh Anh','hourly_minor':1500,'inactive_from':'2026-11-10'})
 act(owner,'tax',{'rate_bps':2000})
 now[0]=datetime(2026,12,1,9,tzinfo=UTC);ops.accrue_payroll(manager,'q1','2026-11','2026-11-30','nov-payroll')
 output={'mode':'read_only_synthetic_role_preview','notice':'Ba vai trò minh họa. Chấm công và ghi giao dịch thật cần backend; dữ liệu dưới đây không phải ca đang diễn ra.',
         'cashier':cashier,'manager':ops.management(manager,'q1','2026-11','2026-11-08'),'owner':ops.owner_summary(owner,'2026-11'),
         'forecast_notice':'Chưa đủ lịch sử đã khóa để dự báo. Không tạo số dự báo giả.'}
 # The activation key is never part of the output object.
 Path('dist/workspace/'+('demo-eur.json' if currency=='EUR' else 'demo.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2))
 print('Built synthetic cashier/manager/owner views; payroll gross:',output['manager']['payroll']['gross_minor'])
