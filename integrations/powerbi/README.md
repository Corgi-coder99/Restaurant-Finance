# Power BI handoff — chưa tạo hay triển khai PBIX

## Bản chạy thử trên Desktop
1. Chạy pipeline. Đọc `gold/current.json` để chọn **một** thư mục snapshot; không gộp tất cả snapshot bằng Folder Combine vì sẽ nhân đôi dữ liệu.
2. Get Data > Text/CSV: nhập fact_monthly_pnl.csv, dim_branch.csv, dim_month.csv trong snapshot đó.
3. Đặt khóa nhánh/document dưới dạng Text; tiền VND: Whole Number; month_start: Date; tỷ lệ: Decimal Number. Các bảng đã ở mức chi nhánh/tháng, không có dữ liệu từng món.
4. Quan hệ một-nhiều, single direction: dim_branch[id] -> fact_monthly_pnl[branch_id]; dim_month[month_start] -> fact_monthly_pnl[month_start]. Không tạo quan hệ giữa các fact. dim_month có một dòng/tháng, không phải bảng ngày đầy đủ; chưa dùng DATEADD/TOTALYTD trên bảng này.
5. Tạo từng measure trong measures.dax. Tỷ lệ phải tính từ tổng doanh thu/chi phí theo bộ lọc, không cộng hay trung bình phần trăm từng dòng. Chia VND cho 1.000.000 nếu hiển thị triệu.
6. Trang Tổng quan: 4 KPI, biểu đồ đường doanh thu/lợi nhuận theo tháng, cơ cấu chi phí, so sánh chi nhánh. Trang Mặt bằng: tiền thuê, tỷ lệ thuê/doanh thu, thay đổi theo kỳ. Bộ lọc: chi nhánh/tháng. Tooltip ghi rõ lợi nhuận trước khấu hao, lãi vay và thuế.

Không tạo card tổng công nợ, dòng tiền hay tồn kho từ dataset này vì chưa có fact tương ứng. File local khi lên Power BI Service cần nguồn dữ liệu/gateway được cấu hình hoặc chuyển sang Fabric; không hứa tự cập nhật từ máy cá nhân.

## Fabric
Notebook mẫu ở ../fabric nạp một snapshot đã duyệt thành bảng Delta có version. Chọn các bảng của cùng một snapshot cho semantic model và đặt tên model tương ứng như trên. Direct Lake là lựa chọn khi workspace/capacity và quyền truy cập phù hợp; cần kiểm tra trong tenant thực tế. Chuyển toàn bộ model sang snapshot mới sau khi notebook thành công; mẫu chưa tự sửa model hay refresh Power BI Service.

## Kiểm soát truy cập khi triển khai
RLS theo chi nhánh cần bảng phân quyền user–branch và kiểm thử View as; chưa triển khai. Không dùng bộ lọc giao diện làm cơ chế phân quyền. Nếu nhúng báo cáo vào app, cần thiết kế danh tính và quyền riêng; không dùng Publish to web cho dữ liệu tài chính nội bộ.

Tài liệu chính thức:
- https://learn.microsoft.com/power-bi/guidance/star-schema
- https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview
