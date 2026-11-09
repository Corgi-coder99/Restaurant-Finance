"""Generate a real SQL-backed scenario and static replay snapshots for the online UI."""
import json
import tempfile
import secrets
from pathlib import Path
from backend.erp.service import ERP

def scenario(erp):
    steps=[];refs={}
    def post(title,kind,**values):
        result=erp.post({'kind':kind,'branch_id':'q1','date':'2026-11-08',**values},f'demo-{len(steps)}')
        steps.append({'title':title,'result':result,'report':erp.report('q1',end='2026-11-08')})
        return result['document_id']
    post('Góp vốn ban đầu vào ngân hàng','capital',amount_minor=500000,payment='bank')
    refs['rice']=post('Nhập gạo và ghi công nợ nhà cung cấp','purchase',item_id='rice',quantity=10000,net_minor=10000,tax_minor=1000,payment='credit')
    refs['chicken']=post('Nhập thịt gà và ghi công nợ','purchase',item_id='chicken',quantity=15000,net_minor=30000,tax_minor=3000,payment='credit')
    post('Thanh toán tiền gạo qua ngân hàng','pay',invoice_id=refs['rice'],amount_minor=11000,payment='bank')
    post('Thanh toán tiền thịt gà','pay',invoice_id=refs['chicken'],amount_minor=33000,payment='bank')
    post('Bán 10 phần cơm gà: ghi doanh thu và giá vốn','sale',items=[{'product_id':'rice_chicken','quantity':10}],tax_minor=1200,payment='cash')
    post('Ghi chi phí thuê mặt bằng','expense',category='rent',net_minor=2000,tax_minor=0,payment='bank')
    refs['asset']=post('Mua bàn ghế: ghi tài sản và dòng tiền chi','asset',name='Bàn ghế phòng ăn',net_minor=60000,tax_minor=12000,life_months=24,payment='bank')
    post('Khấu hao bàn ghế tháng đầu','depreciate',asset_id=refs['asset'])
    post('Đặt mục tiêu dự phòng tiền mặt','reserve',target_minor=20000)
    return {'mode':'read_only_replay_from_python_sql','currency':erp.currency,'jurisdiction':erp.jurisdiction,
        'notice':'Dữ liệu mẫu. Tiền thuế được nhập minh họa, không phải cấu hình thuế UK/EU. Các bước được tính thật bằng Python/SQL; chưa phải giao dịch trên máy chủ online.',
        'steps':steps}

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder:
        result=scenario(ERP(Path(folder)/'demo.sqlite3','GBP','GB',audit_key=secrets.token_bytes(32)))
    target=Path('dist/erp/demo.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('Generated SQL-backed replay:',target,'steps:',len(result['steps']))
