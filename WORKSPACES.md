# Bếp Finance — POS và ba vai trò

## Bản demo và dữ liệu thật

Trang `/` là cổng chọn vai trò. `/workspace/` có sơ đồ bàn, menu hình minh họa, combo, thanh toán và cài đặt quản lý. Bản Sites chạy tĩnh: có thể thử thêm món, thanh toán minh họa, sửa tên/giá mẫu và in, nhưng không lưu lên máy chủ, không thu tiền thẻ và không gửi email. Đổi tiền tệ hoặc tải lại sẽ đặt lại dữ liệu thử. Hai tệp `demo.json` (GBP) và `demo-eur.json` (EUR) là hai sổ giả lập độc lập; không dùng như tỷ giá thị trường.

Mỗi dòng menu có tên VI/EN/FR/DE; giao diện dùng khóa dịch đầy đủ, không dịch dò theo văn bản DOM. Nhân viên, địa chỉ và tên chương trình do người dùng nhập được giữ nguyên. Lỗi API có thông báo bản địa hóa; chi tiết kỹ thuật giữ ngôn ngữ gốc trong mục đóng mặc định.

## Chạy backend Python/SQL

Python 3.11+, cài `backend/requirements.txt`. Backend hiện dùng SQLite; triển khai nhiều cơ sở quy mô lớn cần vận hành, migration PostgreSQL và kiểm định riêng.

Cấu hình qua môi trường máy chủ hoặc kho bí mật, không ghi bí mật vào mã nguồn:

- `BEP_AUDIT_KEY`: khóa ngẫu nhiên ít nhất 32 ký tự, giữ riêng khỏi DB.
- `BEP_ERP_DATABASE`: đường dẫn sổ. `BEP_ERP_CURRENCY=GBP` và `BEP_ERP_JURISDICTION=GB`, hoặc `EUR` và mã quốc gia thực tế, ví dụ `FR`.
- `BEP_AUTH_DATABASE`: DB tài khoản riêng, mặc định `backend/data/accounts.sqlite3`.
- `BEP_ALLOWED_HOSTS`: hostname được phép.
- `BEP_COOKIE_SECURE=true` mặc định; luôn bật khi dùng HTTPS thật. Chỉ đặt `false` nếu chạy thử trên HTTP localhost.

Một sổ không được đổi đồng tiền sau khi đã khởi tạo. Cấu hình sổ EUR riêng khi cần, không đổi ký hiệu GBP thành EUR trên số liệu đã ghi. Chưa triển khai hợp nhất đa tiền tệ hay nguồn FX trực tiếp.

Tạo chủ đầu tiên trên máy chủ tin cậy:

```sh
python -m backend.accounts.cli --email owner@example.com --name Owner --branches q1 td dn
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

CLI hỏi mật khẩu 12–128 ký tự, không đưa mật khẩu vào tham số lệnh. Vào trang chủ từ máy chủ này → Chủ → Đăng nhập. Mỗi người một tài khoản, không dùng chung một mật khẩu cho cả chức danh. Chủ tạo quản lý/thu ngân; quản lý chỉ tạo thu ngân trong cơ sở được cấp. Tạo hồ sơ nhân viên, sau đó liên kết tài khoản thu ngân với employee_id tương ứng. Quản lý muốn chấm công cũng cần employee_id.

Trong cơ sở EU, vào cài đặt cơ sở chọn múi giờ IANA trước khi bắt đầu ca (ví dụ Europe/Paris, Europe/Berlin, Europe/Dublin). GB mặc định Europe/London; có thể cấu hình riêng từng cơ sở.

Token `BEP_ERP_USERS` cũ vẫn được hỗ trợ cho tích hợp/tác vụ quản trị, không phải mật khẩu giao diện. Không chia sẻ token quản trị với thu ngân.

## Gmail và khôi phục mật khẩu

Tính năng đã có backend nhưng cần dịch vụ gửi thư. Đặt qua môi trường bảo mật:

- `BEP_PUBLIC_URL=https://your-restaurant.example` — URL HTTPS chuẩn, không query/fragment.
- `BEP_SMTP_HOST=smtp.gmail.com`, `BEP_SMTP_PORT=465`.
- `BEP_SMTP_USER`, `BEP_SMTP_PASSWORD`, `BEP_SMTP_FROM`: tài khoản gửi được cấp quyền; với Gmail thường cần mật khẩu ứng dụng và xác minh hai bước theo chính sách tài khoản Google. Không dùng mật khẩu Gmail chính trong mã nguồn.

Khôi phục gửi về email tài khoản đã đăng ký, không phải địa chỉ khác do quản lý chỉ định. Liên kết ngẫu nhiên hết hạn sau 15 phút, dùng một lần; yêu cầu mới vô hiệu liên kết cũ. Token nằm trong fragment URL và bị xóa khỏi thanh địa chỉ trước khi gọi API. Đổi/khôi phục mật khẩu vô hiệu hóa phiên đang đăng nhập. Thông báo yêu cầu khôi phục không xác nhận email có tồn tại.

Mật khẩu băm scrypt với salt riêng; token phiên chỉ lưu HMAC trong DB, cookie HttpOnly/SameSite=Strict/Secure. Quyền tài khoản và phiên được ký, có hạn và phiên bản mật khẩu. API ghi bằng cookie đòi Origin cùng miền. Có giới hạn đăng nhập theo tài khoản và giới hạn API theo IP/quá trình. Chưa có SSO/MFA riêng trong ứng dụng; trước triển khai thực tế cần kiểm thử xâm nhập, giám sát, giới hạn phân tán, sao lưu và diễn tập phục hồi. Đây không phải bảo đảm không thể bị hack.

## POS, menu và VAT

Thu ngân chọn bàn → chọn món qua hình → lưu đơn → thanh toán → in phiếu. Combo là món có giá riêng và định lượng tổng từ các thành phần; không cho combo lồng nhau. Món bán phải đang bật. Món không có định lượng là hàng không quản lý kho; nước mẫu hiện thuộc nhóm này, cần cấu hình nguyên liệu thực tế trước sử dụng.

Đơn bàn có revision: sửa đồng thời hoặc thanh toán lại bị chặn; ghi sổ, xuất kho, dùng chìa khóa và đóng đơn cùng một giao dịch SQL. Idempotency-Key chống ghi trùng khi thử lại. Giá thật lấy từ backend, không nhận giá tùy ý từ máy thu ngân. Khi tổng tiền dự kiến không còn đúng, backend yêu cầu kiểm tra lại.

Giá menu gồm VAT. Cấu hình VAT riêng theo món/cơ sở, không giả định một mức hợp pháp chung cho UK/EU. Giảm giá phân bổ theo từng dòng bằng số nguyên penny/cent, sau đó tính giá chưa VAT và VAT từng dòng với cách làm tròn nửa lên. Python và JavaScript dùng phép tính nguyên chính xác (BigInt cho phép nhân bên trình duyệt). Thuế và lợi nhuận phải được kế toán kiểm tra theo quốc gia, loại hàng và phương thức phục vụ; combo pha nhiều nhóm thuế hiện dùng tỷ lệ cấu hình trên combo, chưa tự áp luật phân bổ quốc gia.

Quản lý → Cài đặt: sửa bốn tên món, giá gồm VAT, tỷ lệ VAT, trạng thái bán, thông tin cửa hàng/địa chỉ/mã VAT. Thay đổi lưu thành sự kiện được ký, không sửa master gốc đã ký và không đổi hóa đơn cũ. Phiếu lưu giá, tên, thuế và thông tin cửa hàng tại thời điểm bán.

Phiếu có dòng món, số lượng, đơn giá, giảm giá, tiền chưa thuế, VAT theo mức và tổng thanh toán. In bằng trình duyệt/PDF. Chưa tích hợp driver máy in, giao dịch thẻ, số hóa đơn pháp định, fiscalisation/certification, HMRC/MTD hay cơ quan thuế EU.

## Chấm công và tài chính

Sau xác thực, mở app bắt đầu ca nhân viên; refresh tiếp tục ca cũ. Đóng tab không kết thúc. Cần kiểm tiền đầu ca trước bán; kết thúc/bàn giao ghi giờ nghỉ và tiền thực đếm, đối chiếu chênh lệch. Mỗi ca/quầy đối chiếu riêng; chưa hỗ trợ nhiều thu ngân cùng một ngăn kéo tiền.

Chia ngày theo timezone/DST, không xác minh sự hiện diện vật lý. Tổng thời gian nghỉ được phân bổ qua các ngày. Ca kết thúc phải được duyệt trước ghi lương, ca dài bất thường đánh dấu. Lương gộp theo giờ không gồm tăng ca, nghỉ phép, NI, pension/PAYE hay khấu trừ pháp định. Đơn giá mới áp dụng ca sau; ngừng xếp ca không xóa lương/giờ đã phát sinh và không thay thủ tục chấm dứt hợp đồng.

Lương ghi một lần/tháng đã hoàn tất, tạo chi phí và phải trả. Lãi ngày ước tính theo ca đã kết thúc, tránh trừ lương hai lần. Thuế lợi nhuận do chủ cấu hình chỉ là kịch bản, trống nếu thiếu cấu hình. Dự báo đòi lịch sử khóa đủ dài và kiểm định ngoài mẫu, thiếu dữ liệu thì từ chối.

Xem `SECURITY_AND_QUALITY.md` về chữ ký, đối soát, giới hạn rollback DB và xâm nhập máy chủ/khóa.

## Kiểm thử

```sh
python -m unittest discover -s backend/tests -q
node test-pos.cjs
node test-i18n.cjs
node test-csv.cjs
node test-model.cjs
PYTHONPATH=. python scripts/build-workspace-demo.py
DEMO_CURRENCY=EUR PYTHONPATH=. python scripts/build-workspace-demo.py
```

Kiểm thử bao gồm tài khoản/role/cookie/Origin, băm mật khẩu, hết hạn/dùng lại liên kết, thu hồi phiên, can thiệp quyền, khóa giảm giá, giá/VAT, combo/trừ kho, cạnh tranh đơn bàn, bất biến phiếu cũ, bốn ngôn ngữ và dữ liệu GBP/EUR. Chưa kiểm tra giao diện bằng trình duyệt thật hay máy in/iPhone/Android trong phiên này.
