# Data quality, security, and forecasting

Financial API requests require an authorized role and explicit branch grants. Reports filter source rows before aggregation and use parameterized SQL. A zero revenue denominator produces a null ratio.

Set `BEP_AUDIT_KEY` to a stable random secret of at least 32 characters. Keep it outside source control and store it separately from database backups. Changing it prevents verification of existing signatures. Configure exact hosts with `BEP_ALLOWED_HOSTS`. Legacy `BEP_ERP_USERS` entries include a name, role, explicit branches, and optional expiry. Deploy separate servers and databases for separate legal entities.

## Ledger integrity

The operations ledger verifies HMAC signatures, journal balance, inventory movements, and closed periods before posting, reporting, or exporting. The HTTP middleware checks origins for writes, limits body size and request rates, and sets security and cache headers. Rate limits are per process. Keep verified backups and test recovery because a restored older database may still contain valid signatures.

Back up and reconcile an unsigned legacy ledger before sealing it:

```sh
python -m backend.erp.cli --db PATH seal-legacy --reviewer NAME --reason RECONCILIATION_REFERENCE
```

This signs the reviewed state and does not replace source reconciliation.

## Analytics period review

```sh
python -m backend.cli review-period --branch q1 --month 2025-12 --status complete --reviewer NAME
python -m backend.cli forecast --branch q1 --horizon 3 --as-of 2026-01-01
```

Use `zero` only for a month confirmed to have no entries. Changes to reviewed data invalidate the approval. Review each required period before forecasting. The operations forecast uses verified, closed periods.

Rolling-origin evaluation compares the last observation, trailing three-month mean, and a twelve-month seasonal baseline. A final holdout is excluded from model selection. The forecast refits after evaluation, and profit is calculated from the component forecasts. Supply an explicit cutoff for historical analysis.

The static site serves fixtures. The security middleware applies to the deployed Python backend. See [deployment](DEPLOYMENT.md) for HTTPS and persistent storage.
