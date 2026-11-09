# Enterprise POS and accounting staging

This repository provides a normalized CSV and XLSX staging contract for POS exports and a reconciliation helper. The example file is synthetic. Direct L’Addition Suite, Sage, and SAP API clients are not implemented.

```sh
python -m backend.connectors.pos_staging integrations/enterprise/pos-contract.example.csv --config integrations/enterprise/pos-contract.example.json --source-id demo-pos-october
```

Each row represents a closed POS session. The adapter validates IDs, dates, currency, status, and the net-plus-tax reconciliation. It stores amounts in minor units, supports negative net amounts in staging, and separates totals by provider, company, branch, month, and currency. Use the same source ID and `--replace` for revisions.

Use `reconcile(pos_totals, ledger_totals)` to compare normalized branch, month, currency, and net amounts. Do not add POS sales to the same sales already recognized in the ledger. The legacy VND Gold dataset is separate from multi-currency staging.

Before building a direct connector, obtain the vendor's authorized API documentation, confirm product and account scope, and validate the mapping against reconciled sample exports. Store credentials on the server.

- [L’Addition Suite](https://www.laddition.com/fr/laddition-suite)
- [Sage Intacct developer portal](https://developer.sage.com/intacct)
- [SAP Business One documentation](https://help.sap.com/docs/SAP_BUSINESS_ONE)
