"""Start the authenticated application with an initialized persistent ledger."""
import os
from urllib.parse import urlsplit

import uvicorn

from backend.erp.router import service


def main():
    if len(os.environ.get('BEP_AUDIT_KEY', '')) < 32:
        raise SystemExit('Set a persistent BEP_AUDIT_KEY of at least 32 characters.')

    public_url = urlsplit(os.environ.get('BEP_PUBLIC_URL', ''))
    allowed_hosts = os.environ.get('BEP_ALLOWED_HOSTS', '').split(',')
    if public_url.scheme != 'https' or not public_url.hostname or public_url.hostname not in allowed_hosts:
        raise SystemExit('Set an HTTPS BEP_PUBLIC_URL and include its host in BEP_ALLOWED_HOSTS.')
    if os.environ.get('BEP_COOKIE_SECURE', 'true') == 'false':
        raise SystemExit('Secure session cookies are required.')

    service()
    uvicorn.run('backend.api:app', host='0.0.0.0', port=8000,
                forwarded_allow_ips=os.environ.get('BEP_TRUSTED_PROXY_IPS', '127.0.0.1'))


if __name__ == '__main__':
    main()
