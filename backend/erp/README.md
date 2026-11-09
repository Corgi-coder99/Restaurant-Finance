# Bếp Operations — quy trình nhà hàng MVP

Bản lõi tự xây bằng Python + SQLite, độc lập L’Addition/Sage/SAP. Không phải bản thay thế đầy đủ cho ERP thương mại; chưa có chứng nhận tài chính, POS fiscal hoặc HMRC. Online /erp/ là **replay chỉ đọc** từ 10 bước đã chạy thật bằng Python/SQL. Backend thực thi và lưu nghiệp vụ khi chạy cục bộ.

## Phần chạy được
- Một pháp nhân / một database / một đồng tiền và quốc gia, nhiều chi nhánh. GBP (GB) mặc định; có thể tạo ledger EUR với country riêng, hoặc VND. Không hợp nhất ngoại tệ hay tự quy đổi.
- Góp vốn -> mua nguyên liệu vào kho (tiền ngay hoặc công nợ) -> trả nhà cung cấp.
- Món cơm gà mẫu có định lượng -> bán thu ngay/khách mua chịu -> ghi doanh thu/thuế -> giảm kho và ghi giá vốn -> thu công nợ từng phần.
- Chi phí nhân sự, thuê mặt bằng, vận hành khác; chi phí công nợ chưa trả có thể đảo bằng chứng từ mới. Chưa hỗ trợ refund hàng bán/mua hoặc hủy nghiệp vụ có kho.
- Mua tài sản (bàn ghế) -> dòng tiền hoặc công nợ -> khấu hao hàng tháng. Mục tiêu dự phòng thanh khoản không ghi thành chi phí.
- Double-entry: tổng Nợ = Có trước commit; nghiệp vụ + kho + công nợ ghi cùng SQL transaction. Thiếu nguyên liệu/tiền, trả vượt nợ hoặc số liệu lỗi -> rollback.
- Idempotency-Key chống gửi lại, kiểm tra nội dung khi tái sử dụng key; chứng từ/dòng sổ đã ghi không update/delete qua SQL triggers và API chỉ có POST. DB administrator vẫn có quyền thay schema; chưa phải log chống can thiệp.
- Khóa kỳ theo chi nhánh; owner/accountant/cashier với phạm vi nghiệp vụ khác nhau. Token bắt buộc cho API. Chưa có giao diện quản trị người dùng, MFA, phân quyền riêng từng chi nhánh hoặc nhiều doanh nghiệp trên cùng server.
- Báo cáo lợi nhuận, số dư tiền, công nợ, kho theo ngày, tài sản, bảng cân đối số dư, lịch sử chứng từ và Gold CSV cho BI.

## Chạy
Từ thư mục dự án, Python 3.11+:

```bash
pip install -r backend/requirements.txt
python -m backend.erp.cli init
python -m backend.erp.run_local
```

Launcher hỏi token bằng ô nhập ẩn, cấu hình owner trong bộ nhớ rồi mở máy chủ local. Không ghi token vào source hay log. Dùng cùng token ở nút Kết nối backend local. Với ledger EUR riêng, dùng --currency EUR --jurisdiction FR --db backend/data/fr-erp.sqlite3 (FR chỉ là ví dụ một pháp nhân ở Pháp).

Cấu hình biến môi trường `BEP_ERP_USERS` là JSON dictionary: key là token do người vận hành tạo, value là object có `name` và `role` (owner/accountant/cashier). Không dùng token ví dụ hoặc lưu vào Git. Các biến tùy chọn:

| Biến | Mặc định |
|---|---|
| BEP_ERP_DATABASE | backend/data/erp.sqlite3 |
| BEP_ERP_CURRENCY | GBP |
| BEP_ERP_JURISDICTION | GB |

Khởi chạy `python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000`, mở `http://127.0.0.1:8000/erp/`, chọn Kết nối backend local và nhập token. Token chỉ nằm trong bộ nhớ tab. Nếu chưa cấu hình token, API từ chối truy cập. Giao diện làm việc tài chính dành owner/accountant; cashier hiện dùng API bán hàng/thu nợ, chưa có màn hình thu ngân riêng.

Máy chủ này chưa được triển khai cloud. Để sử dụng từ điện thoại/máy khác cần triển khai backend có HTTPS và cơ chế danh tính phù hợp, không mở thẳng máy dev ra Internet. Không nhập token vào bản replay online: nút kết nối chỉ mở khi phát hiện backend của cùng origin.

## Sử dụng API và CLI
- GET /api/erp/status: kiểm tra có backend, không trả dữ liệu tài chính.
- GET /api/erp/report?branch=q1&start=2026-11-01&end=2026-11-30: Bearer token của owner/accountant.
- POST /api/erp/documents: Bearer token + Idempotency-Key, JSON nghiệp vụ.
- `python -m backend.erp.cli post payload.json --key document-unique-001` là đường quản trị local, có quyền owner.
- `python -m backend.erp.cli report --branch q1`.
- `python -m backend.erp.cli backup /path/to/new-backup.sqlite3`: backup SQLite nhất quán, từ chối ghi đè file đã có. Restore phải dùng bản sao ở path mới, kiểm tra số dư trước sử dụng; chưa tự động hóa backup/restore.
- `python -m backend.erp.export_gold`: xuất snapshot riêng cho Power BI/Fabric; không trộn với legacy Gold VND.

Ví dụ JSON mua nguyên liệu:
```json
{"kind":"purchase","branch_id":"q1","date":"2026-11-08","item_id":"rice","quantity":10000,"net_minor":10000,"tax_minor":1000,"payment":"credit"}
```
`minor` là pence khi GBP, cent khi EUR, nguyên đồng khi VND. quantity của nguyên liệu mẫu là gram nguyên; quantity bán là số phần nguyên. Danh mục mẫu có rice, chicken và rice_chicken; chưa có CRUD danh mục/công thức/giá trong UI. Chi nhánh q1/td/dn chỉ là seed minh họa, không xác định quốc gia. Một ledger khác phải dùng database khác.

Các kind: capital / purchase / sale / pay / collect / expense / asset / depreciate / reserve / reverse_expense / close_period. Xem demo.py và tests/test_erp.py cho payload. Phải ghi theo thứ tự ngày; không tự tính lại giá vốn của giao dịch backdate. Kỳ đã khóa chưa có chức năng mở lại trong MVP.

## Chính sách kế toán minh họa
- Giá vốn xuất kho: bình quân di động trên giá trị tồn và định lượng; làm tròn xuống đơn vị tiền nhỏ nhất ở từng lần dùng, giữ phần dư trong kho và xuất hết giá trị khi dùng hết lượng còn lại. Chưa có lô/hạn dùng/hủy hao hụt/chuyển kho.
- Thuế nhập tay, không suy luận VAT từ quốc gia hay mặt hàng. Tài khoản thuế đầu vào chỉ là số chờ đối soát, chưa khẳng định được khấu trừ. Demo dùng số thuế giả lập, không phải mức thuế cho đồ ăn/bàn ghế ở UK/EU.
- Khấu hao đường thẳng, giá trị thu hồi 0, bắt đầu tháng mua, đủ tháng, chia dư theo minor unit để tổng khấu hao đúng nguyên giá. Yêu cầu tháng liên tiếp; chưa mô hình ngày đưa vào sử dụng, phân bổ theo ngày, thay tuổi thọ hay thanh lý.
- Dự phòng là mục tiêu tiền mặt, không phải provision pháp định, không tạo bút toán hay chuyển tiền.
- Lợi nhuận trước lãi vay/thuế có khấu hao; số dư tiền sau mục tiêu dự phòng chưa trừ mọi nghĩa vụ, không phải lợi nhuận phân phối.
- Đồng tiền báo cáo trong cùng ledger không thay đổi. Không hỗ trợ mua bán bằng ngoại tệ hoặc chênh lệch tỷ giá.

## Kiểm thử / dữ liệu minh họa
`python -m unittest discover -s backend/tests -v`. `python -m backend.erp.demo` tạo lại dist/erp/demo.json bằng một database tạm, không ghi vào database vận hành.

Ví dụ sau 10 bước: doanh thu £120, giá vốn £40, thuê £20, khấu hao £25 -> lợi nhuận £35. Tiền mặt £132 và ngân hàng £3,820; mua bàn ghế £600 + thuế nhập thử £120 đã làm giảm tiền nhưng nguyên giá không bị trừ toàn bộ vào lợi nhuận. Reserve £200 chỉ giảm chỉ tiêu tiền sau mục tiêu dự phòng.

## Các phần cần có trước vận hành thương mại
Hoàn thiện catalog/POS (bàn, bếp, giảm giá, split bill, hoàn/hủy, chốt ca), danh bạ khách/nhà cung cấp, đơn mua–nhận hàng–hóa đơn–đối soát, payroll, đối soát ngân hàng, ngân sách/phê duyệt, công nợ và kỳ chốt đầy đủ. Thêm hóa đơn/số chứng từ pháp định, attachments/OCR, retention, backup định kỳ, quan sát hệ thống, PostgreSQL/migration, quản lý người dùng theo tổ chức, kiểm thử bảo mật và kiểm thử trình duyệt. Kết nối pipeline Bronze–Silver–Gold nhập ngoài vào ledger cần bước staging/duyệt riêng, chưa tự ghi vào sổ này.

UK: cần triển khai và đánh giá đáp ứng Making Tax Digital for VAT nếu áp dụng; chưa có gửi VAT return/HMRC connection. EU: cấu hình theo từng Member State, e-invoicing/fiscalization nếu áp dụng, ngôn ngữ/tỷ giá/thuế và chính sách dữ liệu. Không gắn nhãn compliant/certified khi chưa hoàn tất kiểm chứng.

Nguồn chính thức đã kiểm tra:
- https://www.gov.uk/charge-reclaim-record-vat/keeping-vat-records
- https://www.gov.uk/guidance/find-software-thats-compatible-with-making-tax-digital-for-vat
- https://taxation-customs.ec.europa.eu/taxation/vat/vat-businesses/invoicing_en

## Cập nhật toàn vẹn / quyền truy cập
Mọi lần init/read/write/export cần BEP_AUDIT_KEY giữ ngoài DB; launcher có hỏi key. Người dùng phải có branches cụ thể trong BEP_ERP_USERS. Chứng từ/cấu hình/kho/kỳ khóa được kiểm tra bằng HMAC trước xử lý. Database cũ cần review và seal-legacy, không tự ký lại. Xem ../../SECURITY_AND_QUALITY.md cho migration, giới hạn chống rollback và API /api/erp/forecast trên kỳ đã chốt. Không còn đúng phần mô tả cũ rằng log chỉ có SQL triggers; nay có thêm HMAC nhưng vẫn chưa là audit log độc lập khỏi máy chủ.
