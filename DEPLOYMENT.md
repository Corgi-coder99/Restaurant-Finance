# Deploy Bếp Finance

The Docker image serves the web application and FastAPI from the same origin. A persistent volume holds the operations ledger, account database, and analytics database. Signed-in staff access live data according to their assigned branch and role.

1. Prepare a Docker host and HTTPS reverse proxy. Keep the following environment file outside the repository. Generate a persistent random audit key of at least 32 characters and retain it for upgrades and recovery.

   ```dotenv
   BEP_PUBLIC_URL=https://finance.example.com
   BEP_ALLOWED_HOSTS=finance.example.com
   BEP_AUDIT_KEY=<replace-with-a-persistent-random-secret>
   BEP_ERP_CURRENCY=EUR
   BEP_ERP_JURISDICTION=FR
   BEP_TRUSTED_PROXY_IPS=<proxy-address-seen-by-the-container>
   ```

2. Build the image, create a volume, and provision an owner. The CLI prompts for the password.

   ```sh
   docker build -t bep-finance .
   docker volume create bep-finance-data
   docker run --rm -it --env-file .env -v bep-finance-data:/data bep-finance \
     python -m backend.accounts.cli --email owner@example.com --name "Restaurant owner" --branches q1
   docker run -d --name bep-finance --restart unless-stopped --env-file .env \
     -p 127.0.0.1:8000:8000 -v bep-finance-data:/data bep-finance
   ```

3. Forward traffic to `127.0.0.1:8000`. Preserve the public Host header, overwrite `X-Forwarded-Proto` with `https`, and trust only your proxy address. Open `/workspace/?role=owner&currency=EUR`, sign in, and configure tables, menu items, staff, and business details.
4. Back up SQLite consistently and keep the audit key separately. Follow the [ledger guide](backend/erp/README.md) for backup and the [workspace guide](WORKSPACES.md) for SMTP recovery settings.

Validate payment terminals, dedicated printers, automatic receipt delivery, and applicable fiscal requirements separately before customer service. The current email action opens a receipt draft.
