# L’Addition Suite, Sage và SAP — tích hợp doanh nghiệp

## Trạng thái thực tế
Đã xác nhận người dùng muốn **L’Addition Suite**, không phải ADDISON của Wolters Kluwer. Chưa có quyền API, tài liệu endpoint của tài khoản L’Addition, phiên bản Sage/SAP, hoặc kết nối doanh nghiệp thực tế. Không có connector ChatGPT tương ứng trong phiên làm việc này.

Đã xây adapter **contract xuất POS chuẩn hóa** (CSV/XLSX) và đối soát, không phải native API client được L’Addition chứng nhận. Tệp example là dữ liệu giả lập tự định nghĩa; tên cột không khẳng định giống export/API chính thức. Cần ánh xạ mẫu export thật hoặc payload đã được cấp tài liệu trước khi dùng.

## Hệ thống và vai trò
- L’Addition: doanh số, phiên đóng ca/ngày kinh doanh, thuế; chi tiết món/phương thức thanh toán nếu quyền API/nguồn xuất cung cấp. Nhà cung cấp công bố có API/tích hợp đối tác và export Excel/kế toán.
- Sage: số kế toán/chi phí theo phiên bản. Sage Intacct có REST API, nhưng Sage 50/100/Intacct không dùng chung giao thức/đăng nhập hay mô hình dữ liệu.
- SAP: Business One có Service Layer HTTP/OData; S/4HANA cần chọn API/CDS/OData được phát hành phù hợp với hệ thống và quyền của doanh nghiệp. Không coi Business One client là S/4 client.

Luồng mục tiêu: adapter API hoặc file -> Bronze -> staging POS/kế toán tách biệt -> đối soát -> chọn nguồn doanh thu chuẩn -> Silver/Gold -> API app/Power BI. Không cộng doanh thu POS với doanh thu đã ghi nhận trong Sage/SAP. Báo cáo vận hành có thể dùng POS còn báo cáo đã chốt dùng sổ cái; đánh dấu nguồn và thời điểm cập nhật.

## Bản chạy được ngay
```bash
python -m backend.connectors.pos_staging integrations/enterprise/pos-contract.example.csv --config integrations/enterprise/pos-contract.example.json --source-id demo-pos-october
```
Có thể chạy lại cùng lệnh để kiểm tra không ghi trùng. Nguồn sửa cùng source-id cần --replace. SQLite trong backend/data/connector_staging chỉ là staging, tách khỏi Gold VND của backend cũ.

Contract một dòng/phiên đóng ca: restaurant_id, close_id, business_date, currency, net_sales, tax, gross_sales, status. net_sales đã sau giảm giá/hoàn tiền theo contract nguồn; không trừ giảm giá lần nữa. gross_sales = net_sales + tax. Đây là kiểm tra số học, chưa xác thực tính đầy đủ hay tính thuế theo luật.

- Ánh xạ tên cột và chi nhánh trong JSON config; sheet Excel mặc định pos_closes. Chọn decimal_separator rõ ràng, không đoán dấu chấm/phẩy theo địa phương.
- Dùng Decimal, lưu tiền theo minor unit: EUR cents, VND nguyên đồng. Báo cáo nhóm riêng theo provider/company/branch/month/currency. Không quy đổi tỷ giá.
- Kiểm tra trạng thái đã đóng, ID, ngày ISO, tiền, net+tax=gross và khóa trùng provider/company/restaurant/close. ID khóa không chứa ngày để một phiên được sửa ngày không bị tạo bản sao.
- Giữ raw Bronze SHA-256, Silver có số dòng/branch và cấu hình; lỗi theo run vào sync_runs/quarantine. Lô lỗi không thay số staging đang dùng.
- Đối soát dùng `reconcile(pos_totals, ledger_totals)` với branch_id/month/currency/net_minor; trả matched/review_required/missing_source. Không cộng hai nguồn. Nguồn sổ cái đầu vào phải được adapter kế toán xác nhận phạm vi/tiền tệ trước; adapter Sage/SAP chưa triển khai.
- Hỗ trợ net âm trong staging để không đánh mất hoàn tiền; Gold VND cũ chưa hỗ trợ số âm/đa tiền tệ nên **chưa publish staging này vào báo cáo lợi nhuận**.
- Một worker cục bộ, không có lịch chạy, CDC/cursor hay retry mạng: bản này không gọi mạng. Tách credential khỏi CSV/JSON config và frontend khi triển khai API thật.

## Điều kiện để bật kết nối trực tiếp
1. Xác định quốc gia, đồng tiền, nhà hàng, múi giờ/ngày kinh doanh, quyền lấy lịch sử và module L’Addition đang bật.
2. Lấy tài liệu API và đường cấp quyền chính thức từ L’Addition/đối tác tích hợp. Không suy đoán endpoint hoặc dùng khóa của đối tác khác cho Bếp Finance.
3. Xác định chọn direct API hay trung gian được cấp phép. Chift có công bố connector L’Addition, nhưng cần xác minh phạm vi dữ liệu và hợp đồng riêng; chưa có kết nối Chift trong dự án.
4. Mẫu export/payload đã ẩn thông tin nhạy cảm để kiểm tra mapping, nhiều mức VAT, hoàn/hủy và đóng ca. Không gửi mật khẩu/API secret qua chat; thiết lập trên backend/secret manager.
5. Triển khai adapter read-only phía máy chủ: token/session theo sản phẩm, phân trang, timeout, retry hữu hạn cho lỗi tạm thời, cursor/watermark chỉ tăng sau dữ liệu được xác nhận, chống trùng và nhập bù các chứng từ cập nhật.
6. Sage/SAP: chốt sản phẩm/version, công ty, chart of accounts, thuế, chi nhánh và quyền đọc. Đối soát một khoảng kỳ với báo cáo nguồn trước khi bật định kỳ.
7. Nâng Gold để xử lý EUR, thuế, số âm, nguồn doanh thu chuẩn và cơ chế publish version; không đẩy số EUR vào cột amount_vnd.

Khi triển khai, mua bàn ghế/tài sản và tiền cọc phải đi theo mapping tài sản/đầu tư/dòng tiền phù hợp, không tự coi toàn bộ là chi phí vận hành. Adapter này chưa nhập nghiệp vụ đó.

## Nguồn đã kiểm tra
- L’Addition Suite: https://www.laddition.com/fr/laddition-suite
- API cho chuỗi: https://www.laddition.com/fr/chaines-et-franchises
- Kế toán/export Sage: https://www.laddition.com/fr/logiciel-caisse-comptabilite-restaurant
- Reporting/export Excel: https://www.laddition.com/fr/logiciel-caisse-gestion-comptabilit%C3%A9
- Chift L’Addition (nguồn từ chính nhà tích hợp): https://www.chift.eu/fr/tools/laddition
- Sage Intacct developer: https://developer.sage.com/intacct
- SAP Business One: https://help.sap.com/docs/SAP_BUSINESS_ONE/f110a154dd0f4c20bf7f3ebca9eeb794/60c7a0b745bd486589f05a1da77041f3.html
