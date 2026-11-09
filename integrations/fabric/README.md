# Microsoft Fabric — mẫu triển khai, chưa kết nối tenant

Fabric phù hợp cho OneLake/Delta và điều phối tác vụ; Power BI đảm nhiệm semantic model và báo cáo. Không cần đưa mọi truy vấn app vào Spark: app đọc bảng tổng hợp qua backend/cache, tránh khởi động Spark theo từng lượt bấm. Chưa nối API app với Fabric SQL endpoint.

`pipeline-plan.json` là **đặc tả thiết kế**, không phải JSON có thể import thành pipeline thật. Các bước Copy, OCR/duyệt, notebook, thông báo, quản lý danh tính và refresh model cần cấu hình trong workspace. Chưa có kết nối Microsoft, capacity hoặc tài khoản dịch vụ trong phiên này.

## Chạy mẫu notebook nạp Gold
1. Tạo workspace/lakehouse phù hợp và gắn default lakehouse vào notebook.
2. Chạy pipeline Python local, lấy snapshot từ `gold/current.json`.
3. Upload **toàn bộ thư mục snapshot** gồm manifest + 3 CSV vào `Files/bep/approved_gold/<snapshot_id>/`.
4. Import `import_approved_gold.ipynb`, sửa parameter `snapshot_id`, chạy sau khi người phụ trách đã đối soát dữ liệu. Notebook dùng pandas/SQL Gold ở bước trước, PySpark/Delta tại bước này.
5. Notebook kiểm tra khóa, số tiền, tỷ lệ và số dòng; tạo 3 bảng Delta có hậu tố snapshot. Chỉ tạo file ready sau khi cả 3 hoàn tất. Retry cùng snapshot kiểm tra bảng đã tồn tại, không append dữ liệu lần nữa. Chưa kiểm thử thực thi trên tenant Fabric.
6. Chọn cả 3 bảng của cùng snapshot trong Power BI. Chuyển model sang snapshot mới như một bước publish riêng sau xác nhận; file ready không tự kích hoạt Power BI. Các bảng versioned tiêu tốn dung lượng: cần chính sách lưu trữ/thu hồi sau khi model không còn tham chiếu.

Mẫu dùng snapshot để đơn giản hóa tính nhất quán, chưa phải pipeline Delta incremental sản xuất. Mở rộng: bronze/silver Delta, MERGE theo business key, phân vùng ngày phù hợp, lineage, kiểm tra tổng hóa đơn/thuế, kho, nhiều doanh nghiệp, watermark/CDC, service principal và phân quyền. Không tự retry lỗi chất lượng dữ liệu. Ghi nhận sự khác biệt giữa Gold SQL đã commit và bước export bị lỗi; rerun source không nhân đôi và có thể tái tạo snapshot.

## Nguồn chính thức đã kiểm tra
- Medallion: https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture
- Activity retry: https://learn.microsoft.com/en-us/fabric/data-factory/activity-retries
- Notebook orchestration: https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run?tabs=python
- Direct Lake: https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview
