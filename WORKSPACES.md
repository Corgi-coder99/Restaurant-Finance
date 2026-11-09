# Workspaces and point of sale

The home page links to the cashier, manager, and owner workspaces. The static site offers sample GBP and EUR ledgers. They are independent fixtures and do not represent a currency conversion. Use [deployment instructions](DEPLOYMENT.md) for persistent live data.

## Run locally

Install `backend/requirements.txt` with Python 3.11 or newer. Set `BEP_AUDIT_KEY` to a persistent random secret of at least 32 characters. Set `BEP_ERP_DATABASE`, `BEP_ERP_CURRENCY`, `BEP_ERP_JURISDICTION`, and `BEP_AUTH_DATABASE` for the intended ledger. A ledger keeps its original currency after initialization. Secure cookies are enabled by default. Set `BEP_COOKIE_SECURE=false` only for local HTTP testing.

```sh
python -m backend.accounts.cli --email owner@example.com --name Owner --branches q1 td dn
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

The owner can create managers and cashiers. Managers can create cashiers for assigned branches. Link cashier accounts to employee records and set each branch's IANA time zone before opening a shift. Legacy `BEP_ERP_USERS` tokens remain available for trusted integrations.

## Password recovery

Configure `BEP_PUBLIC_URL`, `BEP_SMTP_HOST`, `BEP_SMTP_PORT`, `BEP_SMTP_USER`, `BEP_SMTP_PASSWORD`, and `BEP_SMTP_FROM` in the server environment. Recovery goes to the registered email address. The link expires after 15 minutes and can be used once. Password changes revoke existing sessions.

## Orders, VAT, and receipts

Cashiers select a table, add items, review payment, and choose receipt options. The owner can adjust table counts, and the app protects tables with open orders from removal. Server-side pricing and order revisions protect against stale totals. Checkout posts the sale, inventory movements, discount redemption, and order closure in one transaction. Retrying with the same idempotency key avoids a duplicate sale.

Menu prices include VAT. Rates are configurable by item and branch. Discounts are allocated across lines before VAT is calculated using integer minor units and half-up rounding. Combo VAT uses the rate configured on the combo. Receipts retain the sale-time menu and merchant details. Browser printing supports PDF output and the email action opens a draft.

## Shifts and reporting

An authenticated employee can resume an open shift after refreshing. Opening cash is required before sales. Closing records breaks, counted cash, and handover. Approved completed shifts can produce hourly payroll accruals. Payroll excludes statutory deductions and overtime rules. Profit tax estimates are owner-configured scenarios.

See [data integrity and security](SECURITY_AND_QUALITY.md) for operational limits and [the main README](README.md) for checks.
