# Restaurant operations ledger

The Python and SQLite ledger covers purchases, inventory, sales, receivables, payables, expenses, assets, depreciation, liquidity targets, and period closing. Each ledger uses one currency and jurisdiction across authorized branches.

## Run locally

```sh
python -m pip install -r backend/requirements.txt
python -m backend.erp.run_local
```

The launcher requests a token and audit key without echoing them. Open `/erp/` on the local server and use the token to connect. Select a separate database for each currency or legal entity. For example, pass `--currency EUR --jurisdiction FR --db backend/data/fr-erp.sqlite3`. The password-based POS is documented in [Workspaces](../../WORKSPACES.md).

## API and CLI

- `GET /api/erp/status` exposes service status.
- `GET /api/erp/report?branch=q1` requires an authorized financial role.
- `POST /api/erp/documents` accepts an authorized JSON transaction with an `Idempotency-Key`.
- `python -m backend.erp.cli post payload.json --key document-unique-001` posts a local administrative transaction.
- `python -m backend.erp.cli report --branch q1` prints a branch report.
- `python -m backend.erp.cli backup /path/to/new-backup.sqlite3` creates a consistent verified backup and refuses to overwrite a file. Match the CLI database, currency, and jurisdiction to the source ledger.
- `python -m backend.erp.export_gold` exports separate BI data for the operations ledger.

```json
{"kind":"purchase","branch_id":"q1","date":"2026-11-08","item_id":"rice","quantity":10000,"net_minor":10000,"tax_minor":1000,"payment":"credit"}
```

Amounts use pence for GBP, cents for EUR, and whole dong for VND. Example ingredient quantities are in grams. See `demo.py` and the ERP tests for supported transactions.

Transactions post balanced debit and credit lines and update inventory in one commit. Inventory uses moving average cost. Straight-line depreciation starts in the purchase month and distributes rounding differences across the asset life. Liquidity reserves are targets and create no accounting entry. Closed periods cannot be reopened through the current API.

`python -m backend.erp.demo` regenerates the read-only sample replay with a temporary database. Keep the audit key outside the database and review the [integrity and access guide](../../SECURITY_AND_QUALITY.md) before importing legacy data. Fiscal certification, regulated tax filing, and complete commercial accounting workflows require separate validation.
