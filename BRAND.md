# Bếp Finance — bộ nhận diện và hướng dẫn

Bếp Nhỏ là linh vật 2.5D: chú nồi cơm màu kem, mũ đầu bếp, tạp dề xanh, huy hiệu lá vàng. Icon ứng dụng dùng cùng ngôn ngữ tạo hình. Hình tạo riêng cho dự án bằng image generation. Tệp gốc giữ trong /workspace/generated_images; phiên bản web tối ưu trong dist/assets.

Giao diện: xanh rừng #174B40, nền trắng ngà và xanh sage, biểu tượng SVG nét mảnh đồng bộ; chữ Be Vietnam Pro có fallback sans-serif. Tối ưu asset linh vật sang WebP, icon PNG riêng cho favicon và Apple touch icon.

Hướng dẫn 7 bước: chào hỏi, chọn chi nhánh, 4 KPI, cơ cấu chi phí, mô phỏng, nhập thử giao dịch, kết thúc. Native dialog hỗ trợ focus/modal và Escape; có quay lại/bỏ qua/mở lại. Trạng thái hoàn thành hoặc bỏ qua lưu trong localStorage key bep-tour-v2 trên thiết bị; không đồng bộ tài khoản. Hướng dẫn không tự thay giá hoặc ghi giao dịch. Mascot là hướng dẫn cố định, chưa phải chatbot AI.

Mobile: thanh dưới có Tổng quan / Chi phí / Thử giá / Thu chi / Thêm. Menu Thêm chứa dự báo, giá nguyên liệu và thông tin. Thẻ chi nhánh thay bảng hẹp trên điện thoại. Nội dung có nhãn dữ liệu mẫu, giải thích KPI, trạng thái lưu cục bộ và giới hạn dự báo. Công thức tài chính và phạm vi backend không đổi.

Kiểm tra: node --check cho app.js, experience.js; node test-model.cjs; Python unittest cho backend/pipeline. Các tham chiếu asset, ID, symbol SVG được kiểm tra tĩnh. Môi trường không có cua_repl.js nên chưa thực hiện browser QA, chưa xác nhận trên thiết bị iOS/Android thật.
