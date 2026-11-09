# Pipeline Bronze–Silver–Gold chạy local

Đây là bản tham chiếu chạy được với Python/SQLite, không tự tạo workspace Fabric.

```bash
pip install -r backend/requirements.txt
python -m backend.pipeline.runner backend/data/sample_entries.csv --source-id demo_2024_2025
```

- Bronze: giữ nguyên file CSV/XLSX/PDF, tên theo SHA-256. Bản gốc không bị thay thế khi xử lý lại. Kiểm tra checksum nếu file cùng tên đã tồn tại.
- Silver: ánh xạ cột, ngày ISO, tiền nguyên VND, chi nhánh, danh mục, dữ liệu bắt buộc và trùng khóa. JSON theo run_id giữ số dòng nguồn. Không đoán dấu phân cách tiền hay ngày nhập nhằng; không tự thực thi công thức Excel.
- Gold: chỉ nhận lô hợp lệ vào entries + entry_lineage trong một giao dịch SQL. View monthly_pnl phục vụ báo cáo. Xuất fact_monthly_pnl, dim_branch, dim_month dưới dạng CSV theo snapshot. Gold/current.json chỉ chuyển sang snapshot đã xuất xong; không cộng tất cả snapshot.
- Ops: state.sqlite3 có pipeline_runs (stage/status/error/count), bronze_files, pipeline_active, entry_lineage. Dòng không hợp lệ vào quarantine/<run_id>.json; lỗi đọc file/cột thiếu lưu trong pipeline_runs.error. Lỗi lô giữ Gold cũ.

## Nhập Excel
Tạo worksheet `entries`, tiêu đề giống sample_entries.csv. Mỗi dòng là doanh thu thuần hoặc chi phí đã ghi nhận, không phải mọi khoản chi tiền. Tiền thuê phân bổ đúng tháng; tiền cọc không thành chi phí. Không tự đọc hóa đơn Excel bố cục tự do.

Đổi tiêu đề nguồn bằng bản sao config.json: canonical field -> tên cột thực tế. `sheet`, giới hạn file/dòng cũng cấu hình ở đó. Chạy với `--config path/to/config.json`. Không đổi tên trường chuẩn phía Gold chỉ để xử lý một mẫu hóa đơn mới.

## PDF và bước duyệt
```bash
python -m backend.pipeline.runner bill.pdf --source-id invoice_001
# returns file_hash and review_required
python -m backend.pipeline.runner reviewed_bill.csv --source-id invoice_001 --evidence-hash HASH_FROM_PDF --reviewed-by 'Nguoi duyet'
```
PDF có text: trích văn bản theo trang, không tự đoán mọi cấu trúc hóa đơn. PDF scan: chỉ đánh dấu cần OCR; adapter OCR chưa có. PDF không tự ghi vào Gold. Người duyệt chuẩn hóa thành CSV/XLSX theo schema, đối chiếu tổng tiền/thuế/chi nhánh rồi dùng cùng source-id. evidence_hash nối dữ liệu đã duyệt với PDF gốc; reviewer ở CLI mới là thông tin tự khai, chưa là chữ ký/xác thực người dùng. Quy trình duyệt có phân quyền, confidence theo trường và đối soát tổng hóa đơn cần xây thêm.

## Chạy lại và sửa chứng từ
- Cùng source-id + checksum + config + phiên bản + thông tin duyệt: skip ghi SQL, có thể xuất lại snapshot. Không append trùng.
- Bản sửa cùng source-id phải dùng `--replace`. Xóa các dòng thuộc nguồn cũ và thay toàn bộ trong cùng transaction. Bất kỳ xung đột nào đều rollback về nguồn cũ. Không dùng source-id khác cho bản sửa để tránh double count.
- Nếu export lỗi sau khi SQL đã commit: run status export_failed, snapshot cũ vẫn còn; chạy lại cùng đầu vào để xuất lại. API SQL có thể thấy phiên bản mới trước file export, nên khi sản xuất phải thống nhất serving version cho app/BI.
- Source-id là định danh một báo cáo/chứng từ logic; không dùng một id cho tất cả file của nhà cung cấp.
- Muốn phục hồi bản trước: chạy lại Bronze cũ theo cùng source-id với --replace, config và thông tin duyệt tương ứng. Bronze và run log vẫn được giữ.
- Bản local ưu tiên một worker/publisher. SQLite khóa ghi và kiểm tra phiên bản nguồn, nhưng chưa có distributed lock cho xuất snapshot; không chạy nhiều publisher đồng thời. Lịch tự động, retry transient và cảnh báo cloud ở mức thiết kế.

## Nối API local
```bash
BEP_DATABASE=backend/data/lakehouse/state.sqlite3 python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
/api/reports/monthly và /api/forecast đọc Gold SQL thật. UI demo vẫn chưa gọi các API này; link Sites vẫn là bản static cũ.

## Thêm tác vụ mới
1. Thêm adapter vào read_records hoặc transform hàm riêng trước normalize; không thay file Bronze.
2. Cập nhật contract/config nếu cần. Nâng VERSION khi thay quy tắc để file cũ không bị skip sai.
3. Thêm fixture và test cho schema mới, lỗi, replay và rollback; chạy toàn bộ kiểm thử.
4. Chạy lại Bronze trong môi trường test; so sánh số dòng, tổng doanh thu/chi phí theo chi nhánh/tháng trước khi publish.
5. Với thay đổi SQL schema, thêm migration có version và kế hoạch backfill; bản hiện tại chỉ bootstrap schema v1, chưa có công cụ migration tự động.

## Giới hạn hiện tại
Chưa có sổ kép, hoàn tiền, tồn kho chi tiết, khấu hao/thuế, đa tiền tệ, so khớp tổng hóa đơn và dòng hóa đơn, chống sửa log, RLS, OCR, lịch chạy production hoặc tích hợp trực tiếp POS. Khóa trùng hiện là chi nhánh + document_id + line_number; khi nối nhiều nhà cung cấp cần mở rộng thêm supplier/source-system để tránh trùng mã hợp lệ. Không dùng như báo cáo tài chính đã kiểm toán.
