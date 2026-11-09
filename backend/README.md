# Python and SQL backend

The FastAPI backend serves authenticated workspaces and analytics endpoints. The operations ledger and VND analytics ledger are separate. See the [workspace guide](../WORKSPACES.md) and [deployment guide](../DEPLOYMENT.md) for account setup.

## Sample analytics workflow

```sh
python -m pip install -r backend/requirements-dev.txt
python -m backend.cli init
python -m backend.cli import backend/data/sample_entries.csv
python -m backend.cli report --branch q1
python -m unittest discover -s backend/tests
```

SQLite stores integer VND amounts. The CSV must use the sample headers and valid branch, category, and date values. The unique document and line key rejects duplicate imports atomically. Import recognized revenue and expenses, including inventory adjustments where appropriate.

The report aggregates costs and operating profit from SQL. Ratios are null when revenue is zero. Authenticated report and forecast APIs verify period approvals. Forecasting compares several baseline methods on rolling origins, reserves a holdout period, and requires current, reviewed data. See [data quality and forecasting](../SECURITY_AND_QUALITY.md).

The sample CSV contains 360 synthetic records across three branches from January 2024 to December 2025. Use `--as-of 2026-01-01` for a historical forecast after approving the relevant periods.
