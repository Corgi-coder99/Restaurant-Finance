# Backend hiện tại

Ứng dụng POS, tài khoản mật khẩu/email, GBP/EUR, ba vai trò và chấm công: xem [WORKSPACES.md](../WORKSPACES.md). Hướng dẫn đó thay thế phần mô tả API/giao diện VND cũ bên dưới. Các CLI analytics cũ vẫn dành riêng cho dữ liệu VND, không trộn vào sổ ERP GBP/EUR.

---

# Python + SQL analytics

Backend chạy cục bộ, bổ sung cho demo giao diện. SQLite để chạy thử; PostgreSQL là lựa chọn cho triển khai nhiều người dùng (cần migration và driver riêng, chưa triển khai).

## Chạy
Từ thư mục gốc dự án, Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend.cli init
python -m backend.cli import backend/data/sample_entries.csv
python -m backend.cli report --branch q1
python -m backend.cli forecast --branch q1 --horizon 3
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

API tại http://127.0.0.1:8000/docs ; giao diện mẫu tại http://127.0.0.1:8000/ . Giao diện vẫn sử dụng JavaScript và dữ liệu minh họa của bản đầu, chưa gọi API Python. Sites hiện chỉ host static, không chạy Python. Không mở API này công khai: chưa có đăng nhập, phân quyền, đa doanh nghiệp hay kiểm toán đầy đủ.

## Dữ liệu và SQL
`sql/schema.sql`: chi nhánh, bút toán quản trị đã ghi nhận, khóa chống trùng, index và view monthly_pnl. Truy vấn tham số hóa. Tiền lưu theo số nguyên VND, không phải triệu VND. Hiện chỉ hỗ trợ VND, số dương và 5 nhóm doanh thu/chi phí; chưa có hoàn tiền, thuế, khấu hao, trả trước, ghi sổ kép hoặc đa tiền tệ.

CSV phải có đúng các cột trong `data/sample_entries.csv`. branch_id: q1, td, dn. category: revenue, food, labor, rent, other. recognized_date: ngày ghi nhận YYYY-MM-DD. document_id + line_number + branch_id chống trùng. Lỗi bất kỳ từ chối toàn bộ lô; không tự bỏ dòng trùng.

Chỉ nhập doanh thu thuần và chi phí đã phân bổ/điều chỉnh tồn kho. Không nhập trực tiếp mọi hóa đơn mua nguyên liệu thành giá vốn; không coi tiền cọc thuê là chi phí. source chỉ là nguồn tham chiếu, chưa lưu chứng từ gốc. CLI nhập CSV là đường nhập dữ liệu, API hiện chỉ đọc.

## Phân tích và dự báo
Pandas tính tổng chi phí, lợi nhuận vận hành, biên lợi nhuận và tỷ lệ tiền thuê/doanh thu từ tổng hợp SQL. Khi doanh thu bằng 0, tỷ lệ trả null.

NumPy/Pandas thực hiện baseline mùa vụ: lấy số cùng tháng năm trước cho từng thành phần doanh thu/chi phí, sau đó tính lợi nhuận. Cần >=12 tháng liên tục đã hoàn tất; loại tháng hiện tại; không tự điền tháng thiếu bằng 0. Có >=24 tháng thì đo MAE/WAPE doanh thu trên 12 tháng gần nhất bằng dự báo trễ 12 tháng, không lấy dữ liệu tương lai. Chưa có khoảng dự báo thống kê, mô hình ML, hay bộ tối ưu. Backend không tự xác minh dữ liệu tháng đã đầy đủ.

Dữ liệu mẫu gồm 360 dòng giả lập của 3 chi nhánh, 01/2024–12/2025. Kết quả dự báo mẫu 01–03/2026 là dự báo hồi cứu tính từ cuối dữ liệu, không phải dự báo hiện tại. Cần nhập dữ liệu cập nhật đến tháng đã kết thúc gần nhất để dự báo tương lai gần.

## Kiểm thử
```bash
pip install httpx
python -m unittest discover -s backend/tests -v
```
Các kiểm thử: đối soát lợi nhuận, rollback hóa đơn trùng/lỗi, thiếu tháng, dự báo/backtest và API. Tệp JSON đi kèm được tạo thật bằng CLI trên dữ liệu giả lập.

## Cập nhật bảo mật và dự báo (thay thế hướng dẫn baseline cũ)
API tài chính nay yêu cầu token và branches rõ ràng. Forecast cần BEP_AUDIT_KEY và các kỳ được review có chữ ký; report API cũng xác minh review. Không còn tự dùng seasonal naive duy nhất. Dữ liệu mẫu kết thúc 12/2025 phải dùng as_of=2026-01-01 để kiểm định lịch sử, không xem là dự báo hiện tại. Hướng dẫn đầy đủ và migration ở ../../SECURITY_AND_QUALITY.md.
