# Bronze, Silver, and Gold pipeline

```sh
python -m pip install -r backend/requirements.txt
python -m backend.pipeline.runner backend/data/sample_entries.csv --source-id demo_2024_2025
```

Bronze keeps the original file under its SHA-256 digest. Silver maps and validates columns, dates, branch IDs, integer VND amounts, and document keys. Gold commits valid batches and lineage in SQLite, then exports `fact_monthly_pnl.csv`, `dim_branch.csv`, and `dim_month.csv`. Use the snapshot selected by `gold/current.json`. Rejected rows go to quarantine and leave the active dataset intact.

Excel inputs use the `entries` sheet with the sample CSV headers. Pass `--config` to map source columns and configure limits. Formula cells are rejected. Import recognized revenue or expense rows, including appropriate inventory adjustments.

```sh
python -m backend.pipeline.runner bill.pdf --source-id invoice_001
python -m backend.pipeline.runner reviewed_bill.csv --source-id invoice_001 --evidence-hash HASH_FROM_PDF --reviewed-by 'Reviewer'
```

PDF processing extracts available text and flags scanned documents for OCR review. A reviewer must reconcile the source and supply a normalized CSV or Excel file before any rows reach Gold. The reviewer field records an operator-supplied name.

Identical inputs can be replayed without duplication. Use the same source ID and `--replace` for a corrected source. A failed SQL transaction leaves the prior rows in place. If only export fails, rerun the same input to rebuild the snapshot. Use a single snapshot publisher. Set `BEP_DATABASE=backend/data/lakehouse/state.sqlite3` to serve the dataset through the authenticated analytics API. Period approval is required before official reporting and forecasting.
