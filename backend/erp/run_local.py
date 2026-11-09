"""Interactive local launcher; reads an owner access token without echoing it."""
import argparse
import getpass
import json
import os
import uvicorn
from datetime import datetime,timedelta,timezone
from backend.erp.service import ERP

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Start local Bếp Operations MVP')
    parser.add_argument('--currency',choices=['GBP','EUR','VND'],default='GBP')
    parser.add_argument('--jurisdiction',default='GB')
    parser.add_argument('--db',default='backend/data/erp.sqlite3')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    token=getpass.getpass('Đặt access token cho phiên local (ít nhất 16 ký tự, không hiển thị): ')
    if len(token)<16:raise SystemExit('Token cần ít nhất 16 ký tự.')
    audit_key=os.environ.get('BEP_AUDIT_KEY') or getpass.getpass('Khóa kiểm tra dữ liệu (ít nhất 32 ký tự; giữ nguyên cho các lần chạy sau): ')
    if len(audit_key)<32:raise SystemExit('Audit key cần ít nhất 32 ký tự.')
    os.environ['BEP_AUDIT_KEY']=audit_key
    ERP(args.db,args.currency,args.jurisdiction)
    os.environ.update(BEP_ERP_DATABASE=args.db,BEP_ERP_CURRENCY=args.currency,
        BEP_ERP_JURISDICTION=args.jurisdiction,BEP_ERP_USERS=json.dumps({token:{'name':'Local Owner','role':'owner','branches':['q1','td','dn'],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()}}))
    print(f'Mở http://127.0.0.1:{args.port}/erp/ rồi chọn Kết nối backend local. Dùng token vừa đặt.')
    uvicorn.run('backend.api:app',host='127.0.0.1',port=args.port)
