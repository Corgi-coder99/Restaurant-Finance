# Vận hành Bếp Finance

Bản chạy chính phục vụ giao diện và API FastAPI trên cùng tên miền. SQLite lưu trên ổ đĩa bền vững. Dữ liệu mẫu phục vụ trải nghiệm thử khi chưa đăng nhập. Sau khi đăng nhập, workspace đọc và ghi dữ liệu theo quyền của tài khoản.

1. Chuẩn bị máy chủ Docker và reverse proxy HTTPS. Lưu cấu hình dưới đây trong tệp `.env` ngoài kho mã. Đặt khóa ngẫu nhiên ít nhất 32 ký tự và giữ nguyên khóa khi cập nhật hoặc khôi phục dữ liệu.

   ```dotenv
   BEP_PUBLIC_URL=https://finance.example.com
   BEP_ALLOWED_HOSTS=finance.example.com
   BEP_AUDIT_KEY=<replace-with-a-persistent-random-secret>
   BEP_ERP_CURRENCY=EUR
   BEP_ERP_JURISDICTION=FR
   BEP_TRUSTED_PROXY_IPS=<proxy-address-seen-by-the-container>
   ```

2. Tạo image, volume và tài khoản chủ quán. Lệnh tạo tài khoản hỏi mật khẩu tương tác.

   ```sh
   docker build -t bep-finance .
   docker volume create bep-finance-data
   docker run --rm -it --env-file .env -v bep-finance-data:/data bep-finance \
     python -m backend.accounts.cli --email owner@example.com --name "Restaurant owner" --branches q1
   docker run -d --name bep-finance --restart unless-stopped --env-file .env \
     -p 127.0.0.1:8000:8000 -v bep-finance-data:/data bep-finance
   ```

3. Trỏ reverse proxy đến `127.0.0.1:8000`. Giữ header Host của tên miền công khai và cấu hình proxy ghi đè `X-Forwarded-Proto: https`. Chỉ tin địa chỉ proxy thực tế. Mở `/workspace/?role=owner&currency=EUR` và đăng nhập. Sổ mới chưa có giao dịch. Cấu hình thực đơn, bàn, nhân viên và thông tin cửa hàng trước khi thử vận hành.
4. Lưu bản sao SQLite nhất quán và giữ khóa kiểm tra ở nơi riêng. Xem [hướng dẫn sổ vận hành](backend/erp/README.md) để sao lưu và kiểm tra sổ. Cấu hình SMTP theo [hướng dẫn workspace](WORKSPACES.md) nếu cần email khôi phục tài khoản.

Bản này hỗ trợ ghi nhận giao dịch và lập báo cáo. Thanh toán thẻ, máy in chuyên dụng, gửi hóa đơn tự động và quy trình tuân thủ thu ngân cần được kiểm chứng riêng trước khi đưa vào phục vụ khách. Nút email hóa đơn mở bản nháp trong ứng dụng email.
