# Bếp Finance

Bếp Finance kết hợp quản lý bàn và đơn hàng với báo cáo doanh thu, cơ cấu chi phí và lợi nhuận cho chủ nhà hàng.

- **Chạy với dữ liệu của quán:** xem [hướng dẫn triển khai](DEPLOYMENT.md) để chạy giao diện và API cùng tên miền, tạo tài khoản và lưu dữ liệu trên ổ đĩa bền vững.
- **Dùng thử:** bản Sites và các tệp dữ liệu mẫu phục vụ trải nghiệm giao diện.

## Chế độ dùng thử
Mở dist/index.html bằng trình duyệt. Không cần cài thư viện.

Dữ liệu minh họa: 3 chi nhánh; triệu VND; tháng 11/2026. Lợi nhuận vận hành trước khấu hao, lãi vay, thuế. Mô phỏng phân tích độ nhạy, không phải mô hình ML được huấn luyện hoặc OR-Tools. Giá nguyên liệu là giả lập, không thời gian thực. Giao dịch nhập tay chỉ lưu localStorage và chưa cộng vào báo cáo. Kịch bản cũng lưu trên thiết bị.

Kiểm thử: `node test-model.cjs`.

Tham khảo đã đọc trên GitHub: https://github.com/frappe/erpnext và https://github.com/google/or-tools . Không sao chép hay tích hợp mã hai dự án này trong demo. Backend kế toán, nguồn giá, OCR/POS, mô hình dự báo, kiểm soát truy cập và nhật ký kiểm toán cần xây dựng ở giai đoạn tiếp theo.

## Backend phân tích dữ liệu đã bổ sung
Xem [backend/README.md](backend/README.md): Python, SQL/SQLite, Pandas, NumPy, FastAPI; nhập CSV có kiểm tra, tổng hợp lợi nhuận và dự báo mùa vụ cơ sở. Có dữ liệu giả lập và báo cáo JSON được tạo bằng Python. Backend hiện chạy cục bộ, chưa kết nối với giao diện Sites đã xuất bản.

## Bronze–Silver–Gold, Excel/PDF và BI
- Pipeline chạy local: [backend/pipeline/README.md](backend/pipeline/README.md).
- Power BI: bảng Gold theo star schema + [DAX và hướng dẫn](integrations/powerbi/README.md).
- Fabric: [đặc tả pipeline và notebook chuyển snapshot sang Delta](integrations/fabric/README.md), chưa triển khai cloud.
- Colab: [notebook chạy thử Python/SQL, biểu đồ và tải kết quả](notebooks/Bep_Finance_Colab.ipynb).
- `examples/gold` là snapshot thật được sinh từ 360 dòng dữ liệu giả lập; có thể nhập ngay vào Power BI Desktop.

PDF có text được trích xuất để duyệt; PDF scan chưa có OCR. Excel hỗ trợ mẫu dạng bảng, chưa đọc mọi bố cục hóa đơn. Pipeline chưa kết nối với demo Sites online.

## Giao diện và Bếp Nhỏ
Giao diện mới trong dist/experience.css và dist/experience.js: điều hướng mobile, KPI có giải thích, linh vật 2.5D, icon ứng dụng và hướng dẫn người mới 7 bước có thể bỏ qua/mở lại. Xem BRAND.md. Chưa kiểm thử trực tiếp trên trình duyệt/thiết bị thật do công cụ browser QA được yêu cầu không có trong môi trường.

## Tích hợp L’Addition Suite / Sage / SAP
Xem [tích hợp doanh nghiệp](integrations/enterprise/README.md). Đã có staging POS contract CSV/XLSX, phân tách EUR/VND và đối soát doanh thu để tránh cộng trùng POS/kế toán. Chưa có kết nối API trực tiếp hoặc xác thực tài khoản nhà cung cấp; chưa publish dữ liệu staging đa tiền tệ vào Gold VND.

## Bếp Operations — lõi vận hành độc lập
[backend/erp/README.md](backend/erp/README.md): sổ kép Python/SQL với mua–kho–bán–công nợ–thu chi–tài sản/khấu hao–mục tiêu dự phòng–khóa kỳ, API có xác thực và vai trò, backup CLI, Gold export riêng theo ledger GBP/EUR/VND. Giao diện /erp/ xem lại quy trình mẫu online; để ghi/lưu nghiệp vụ thật phải triển khai backend và kết nối tại cùng origin. Chưa thay thế đầy đủ hoặc chứng nhận như hệ thống kế toán/POS thương mại.

## Ngôn ngữ
Bộ chọn VI / EN / FR / DE dùng chung dashboard, tutorial và trang vận hành /erp/. Ghi nhớ trên thiết bị; định dạng số, tiền và ngày theo locale, giữ nguyên currency/thuế/dữ liệu ledger. Xem [I18N.md](I18N.md). Kiểm thử: `node test-i18n.cjs`.

## Bản tăng cường chất lượng và bảo mật
Xem [SECURITY_AND_QUALITY.md](SECURITY_AND_QUALITY.md): auth cho mọi API tài chính, branch grants bắt buộc, HMAC ledger/review, giới hạn HTTP, lọc dữ liệu trước tổng hợp, dự báo rolling-origin + holdout. Đây là thay đổi có chủ đích: ledger cũ chưa ký, token thiếu branches, dữ liệu chưa review/khóa kỳ hoặc quá cũ sẽ bị từ chối thay vì tự tin dùng số liệu.
