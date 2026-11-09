# Bếp Finance

Bếp Finance is a restaurant operations and financial analytics application. The cashier workspace handles tables, orders, payment records, and receipts. The owner workspace explains revenue, costs, and operating margins across branches.

## Run the application

- [Production deployment](DEPLOYMENT.md) covers Docker, HTTPS, persistent storage, and owner account setup.
- [Local workspace setup](WORKSPACES.md) covers staff accounts, POS workflows, and operational settings.
- For a sample-only preview, run `python -m http.server 8000 --directory dist` and visit `http://localhost:8000/`.

The static preview uses sample data. The authenticated FastAPI deployment reads and writes its own SQLite ledger. The POS records payment methods, while receipt email opens a draft in the device's email application.

## Repository guide

| Area | Location |
| --- | --- |
| Web interface and static assets | [dist](dist/) |
| Python, SQLite, and FastAPI | [backend](backend/) |
| Restaurant operations ledger | [ERP guide](backend/erp/README.md) |
| CSV, Excel, and PDF staging | [Pipeline guide](backend/pipeline/README.md) |
| Forecast validation and data integrity | [Security and quality](SECURITY_AND_QUALITY.md) |
| Data analysis walkthrough | [Colab notebook](notebooks/Bep_Finance_Colab.ipynb) |
| BI and external POS handoffs | [Power BI](integrations/powerbi/README.md), [Fabric](integrations/fabric/README.md), [Enterprise connectors](integrations/enterprise/README.md) |

The interface supports English, Vietnamese, French, and German. See the [localization guide](I18N.md).

## Run the checks

```sh
python -m pip install -r backend/requirements-dev.txt
python -m unittest discover -s backend/tests
node test-model.cjs
node test-csv.cjs
node test-i18n.cjs
node test-pos.cjs
```
