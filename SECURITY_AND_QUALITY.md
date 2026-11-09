# Chất lượng dữ liệu, bảo mật và dự báo — phạm vi kiểm chứng

## Kết quả rà soát và thay đổi có hiệu lực
1. API /api/reports/monthly và /api/forecast trước đây đọc không cần xác thực. Nay đều yêu cầu Bearer token, vai trò tài chính và danh sách chi nhánh được cấp **rõ ràng**. Không có branches không có nghĩa được xem tất cả. API ERP đọc/ghi/dự báo cũng kiểm tra branch ở server. Body không được tự gán role/actor/currency hay field ngoài schema nghiệp vụ.
2. API báo cáo lọc **dòng nguồn trước khi tổng hợp**, dùng tham số SQL, kiểm tra ngày ISO/thứ tự ngày và branch. Giữ tiền ở số nguyên, tỷ lệ doanh thu 0 trả null. API phân tích chính thức chỉ trả các tháng có chữ ký review hợp lệ; CLI monthly_report vẫn có thể xem bản nháp để đối soát. Không im lặng biến tháng thiếu thành 0.
3. Kỳ phân tích cần được reviewer xác nhận complete hoặc zero; lưu fingerprint của dữ liệu và HMAC. Forecast/báo cáo kiểm tra lại fingerprint và chữ ký trong cùng read transaction. Dữ liệu sửa/nhập thêm sau review buộc duyệt lại. Review là xác nhận của con người, không chứng minh hóa đơn thực hay dữ liệu đầy đủ.
4. ERP ký baseline dữ liệu cấu hình và chuỗi giao dịch bằng HMAC-SHA256. Chữ ký gồm chứng từ, dòng sổ, dịch chuyển kho, công nợ, tài sản/khấu hao và liên kết chữ ký trước đó. Trước báo cáo/ghi mới/export Gold: kiểm tra chữ ký, tổng Nợ/Có, kho cache khớp dịch chuyển và kỳ khóa khớp chứng từ. Phát hiện sai -> dừng, không tự sửa hay tự ký lại.
5. HTTP backend: body JSON tối đa 64 KiB (cả chunked), từ chối trường JSON trùng và NaN/Infinity, từ chối write khác origin, trusted hosts có cấu hình, rate limit 120 requests/phút/client/process, cache no-store cho API tài chính, CSP/nosniff/referrer policy. Không tin X-Forwarded-For từ client. CSV/XLSX ingestion local có giới hạn và thêm kiểm tra dung lượng giải nén XLSX. Không có API upload PDF/XLSX công khai trong phiên bản này.
6. Token có thể disabled/expires_at; launcher local đặt hạn 8 giờ. Token của UI chỉ ở bộ nhớ tab, không localStorage. API key và audit key không ở source/DB.

## Cấu hình bắt buộc
`BEP_AUDIT_KEY`: bí mật ngẫu nhiên ít nhất 32 ký tự, giữ ở secret manager/biến môi trường bảo vệ, giữ nguyên cho ledger và các review. Không commit hoặc đưa vào log. Khóa khác sẽ không xác minh được dữ liệu đã ký. Chưa có quy trình rotate key tự động.

`BEP_ERP_USERS`: JSON dictionary từ token tới identity gồm name, role và branches. Các trường tùy chọn enabled (bool), expires_at (ISO timestamp có timezone). Chỉ owner/accountant được đọc tài chính, cashier chỉ ghi các nghiệp vụ được cấp quyền và đúng branch. Có scope theo chi nhánh nhưng **chưa có SaaS multi-tenant**; mỗi công ty dùng server/database tách biệt. `BEP_ALLOWED_HOSTS` mặc định localhost,127.0.0.1,[::1],test; triển khai phải đặt host thực, không mở wildcard.

Launcher `python -m backend.erp.run_local` hỏi token và audit key qua getpass, không in bí mật. CLI analytics cũng cần BEP_AUDIT_KEY khi review/dự báo. Khởi chạy lại bằng cùng khóa. API trên demo Sites online vẫn là static replay; middleware này chỉ có hiệu lực ở backend Python được triển khai.

## Database cũ chưa được ký
Không tự động tin hay ký lại lịch sử cũ. Backup vào nơi độc lập, đối soát dữ liệu nguồn và số dư trước. Sau kiểm tra, operator local có thể dùng:
```
python -m backend.erp.cli --db PATH seal-legacy --reviewer NAME --reason RECONCILIATION_REFERENCE
```
Migration tạo baseline có thông tin người duyệt/lý do, kiểm tra cân đối/kho/kỳ rồi ký lịch sử **đang có** trong transaction. Chữ ký không chứng minh lịch sử trước thời điểm migration là chính xác. Không có endpoint API để reset baseline hay tự bỏ qua lỗi xác minh; baseline đã có không được reset bằng lệnh này.

## Duyệt tháng cho analytics VND
```
python -m backend.cli review-period --branch q1 --month 2025-12 --status complete --reviewer NAME
python -m backend.cli forecast --branch q1 --horizon 3 --as-of 2026-01-01
```
`zero` chỉ dùng khi đã xác nhận tháng không có dòng phát sinh. complete không chấp nhận tháng trống. Không tự duyệt dữ liệu thật. Mẫu build-assurance-demo chỉ tạo approval trên CSV giả lập đi kèm, trong database tạm và khóa ngẫu nhiên không lưu.

## Logic dự báo mới
- Chỉ dùng các tháng hoàn tất trước cutoff; cutoff không tương lai. Mặc định yêu cầu dữ liệu tới tháng đã kết thúc gần nhất. Dữ liệu cũ không tự tạo “dự báo tương lai” cho các tháng đã qua. Muốn backtest lịch sử phải truyền as_of rõ ràng.
- Analytics VND: mọi tháng phải có review còn hợp lệ; ERP GBP/EUR/VND: mọi tháng lịch sử phải đã khóa và ledger phải xác minh chữ ký. Khoảng trống chỉ bằng 0 nếu được xác nhận rõ, không suy đoán.
- So sánh last_value, mean_last_3 và seasonal_12 riêng cho doanh thu/từng chi phí. Rolling origins chỉ nhìn quá khứ. Giữ h tháng cuối làm holdout hoàn toàn không dùng chọn mô hình; refit bằng toàn bộ dữ liệu sau khi đánh giá.
- Cần >=6 selection origins. Tối thiểu 17+2*h tháng liên tục (23 tháng với h=3; 29 với h=6). Không đủ -> từ chối thay vì số dự đoán giả. Các thành phần tiền cần không âm; kỳ có reversal tạo thành phần ròng âm cần mô hình/chính sách riêng, hiện từ chối.
- Công bố model/MAE selection, MAE/WAPE doanh thu và MAE lợi nhuận holdout. WAPE khi doanh thu 0 = null, có cảnh báo. WAPE >30% và thay đổi mức hoạt động lớn được gắn review_required. 30% là ngưỡng quản trị minh họa, không phải tiêu chuẩn thống kê hay đảm bảo độ chính xác.
- Lợi nhuận luôn được suy ra từ doanh thu trừ chi phí dự báo, không chạy mô hình lợi nhuận độc lập gây lệch phương trình. ERP có thêm khấu hao và giữ nguyên currency ledger.
- Chưa có khoảng dự báo đã hiệu chuẩn, chưa có holiday/weather/promotion regressors. Holdout ngắn và 3 model cơ sở không chứng minh mô hình “tốt nhất” trong mọi tình huống tương lai. Không dự báo tiền tệ hoặc chính sách thuế.

API ERP thêm GET /api/erp/forecast?branch=q1&horizon=3&as_of=YYYY-MM-DD, có cùng auth/scope. Mẫu ERP 1 ngày không đủ dữ liệu: phải từ chối. Trên UI dashboard, phần evidence chỉ là **backtest dữ liệu giả lập 2024–2025**, không phải dự báo hiện tại; các slider vẫn là kịch bản giả định.

## Giới hạn bảo mật cần biết khi triển khai
HMAC phát hiện sửa nội dung mà không có key; không mã hóa dữ liệu và không ngăn mọi xâm nhập. Chưa phát hiện rollback cả DB về một snapshot cũ hợp lệ hoặc xóa toàn bộ DB rồi tạo mới. Muốn chống rollback cần head/anchor ở kho độc lập có retention/append-only và giám sát ngoài server. Không thể bảo vệ nếu attacker đã lấy cả khóa và quyền máy chủ. Đối chiếu nguồn, tách quyền, backup độc lập và thử restore vẫn cần thiết.

Chưa có SSO/MFA, session UI quản trị, approval 4 mắt, rotation tự động, disk encryption, WAF/gateway phân tán, pentest độc lập hoặc chứng nhận. In-memory rate limit có thể reset khi restart và không bao phủ nhiều worker. CSP của backend không tự áp dụng cho Sites static gateway. Swagger /docs dùng CDN nên bị CSP chặn theo mặc định; dùng /openapi.json hoặc API client thay vì nới script policy cho dữ liệu tài chính.

40 kiểm thử Python và các kiểm thử Node đã chạy đạt ở phiên bản này. Có kiểm thử tấn công giả lập, không phải pentest: bỏ token, token hết hạn, đổi branch, giả role, SQL injection, origin khác, body quá lớn/chunked, rate limit, sửa sổ vẫn cân Nợ/Có, đổi giá catalog/kho, sai audit key, migration cũ, thiếu review, thay dữ liệu sau review, rò rỉ holdout và tính nhất quán lợi nhuận. Chưa có browser QA vì môi trường Sites thiếu cua_repl.js.

Nguồn phương pháp:
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- https://otexts.com/fpp3/toolbox.html

CSV tải từ UI xử lý công thức trong ô văn bản, kể cả khi có khoảng trắng đầu dòng, nhưng giữ số âm kiểu number để không làm sai phân tích Excel. Gold CSV là dữ liệu máy đọc theo contract, chưa có lớp chống công thức riêng cho mọi công cụ bảng tính bên ngoài.
