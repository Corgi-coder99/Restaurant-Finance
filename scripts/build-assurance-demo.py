"""Generate validation evidence only from the bundled synthetic dataset."""
import json
import secrets
import tempfile
from pathlib import Path
from unittest.mock import patch
from backend.analytics import connect,initialize,import_csv,monthly_report,forecast,ROOT
from backend.data_quality import review_period

with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'BEP_AUDIT_KEY':secrets.token_urlsafe(48)}):
    conn=connect(Path(folder)/'sample.sqlite3');initialize(conn)
    import_csv(conn,ROOT/'data/sample_entries.csv')
    output={}
    for branch in ['q1','td','dn']:
        for row in monthly_report(conn,branch):review_period(conn,branch,row['month'],'complete','Synthetic fixture review only')
        output[branch]=forecast(conn,branch,3,'2026-01-01')
    conn.close()
Path('dist/forecast-validation.json').write_text(json.dumps({'mode':'synthetic_historical_validation','history':'2024-01 to 2025-12','cutoff':'2026-01-01','branches':output},ensure_ascii=False,indent=2))
Path('backend/data/sample_forecast.json').write_text(json.dumps(output['q1'],ensure_ascii=False,indent=2))
print('Built synthetic validation evidence for 3 branches; not a current restaurant forecast')
