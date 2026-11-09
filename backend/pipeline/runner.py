"""Bronze -> validated Silver -> atomic SQL Gold. Single local writer reference."""
import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from backend.analytics import connect, initialize, monthly_report, CATEGORIES

VERSION = 'medallion-1.0'
FIELDS = ['branch_id','document_id','line_number','recognized_date','category','amount_vnd','source']
SCHEMA = '''
CREATE TABLE IF NOT EXISTS pipeline_runs(
 run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, file_hash TEXT NOT NULL,
 config_hash TEXT NOT NULL, version TEXT NOT NULL, stage TEXT NOT NULL,
 status TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0,
 error TEXT, started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT);
CREATE TABLE IF NOT EXISTS bronze_files(
 file_hash TEXT NOT NULL, source_id TEXT NOT NULL, original_name TEXT NOT NULL,
 path TEXT NOT NULL, run_id TEXT NOT NULL, PRIMARY KEY(file_hash,source_id));
CREATE TABLE IF NOT EXISTS pipeline_active(
 source_id TEXT PRIMARY KEY, file_hash TEXT NOT NULL, config_hash TEXT NOT NULL,
 version TEXT NOT NULL, run_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entry_lineage(
 entry_id INTEGER PRIMARY KEY REFERENCES entries(id) ON DELETE CASCADE,
 source_id TEXT NOT NULL, run_id TEXT NOT NULL, file_hash TEXT NOT NULL,
 source_row INTEGER NOT NULL, evidence_hash TEXT, reviewed_by TEXT);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON entry_lineage(source_id);
'''

def atomic_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def integer(value):
    # Do not guess locale: 1.234 / 1,234 are ambiguous in financial documents.
    if isinstance(value, bool):
        raise ValueError('Boolean is not a money amount')
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError('Fractional VND not supported')
        value = int(value)
    if not re.fullmatch(r'[0-9]+', str(value).strip()):
        raise ValueError('Use whole VND without separators or currency symbols')
    return int(str(value).strip())

def read_records(raw, extension, config):
    if extension == '.csv':
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers):
            raise ValueError('Duplicate CSV headers')
        rows = []
        for row in reader:
            if None in row or None in row.values():
                raise ValueError('CSV row column count does not match header')
            rows.append(row)
            if len(rows) > config['max_rows']:
                raise ValueError('Row limit exceeded')
        return headers, rows
    if extension == '.xlsx':
        import zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=archive.infolist()
            if len(members)>5000 or sum(m.file_size for m in members)>config.get('max_uncompressed_bytes',80*1024*1024):
                raise ValueError('Excel archive exceeds expanded size limits')
            if any(m.file_size>1024*1024 and m.file_size/max(m.compress_size,1)>1000 for m in members):
                raise ValueError('Suspicious Excel compression ratio')
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
        try:
            sheet = workbook[config['sheet']]
            if sheet.max_row > config['max_rows']+1:
                raise ValueError('Row limit exceeded')
            iterator = sheet.iter_rows()
            cells = next(iterator, ())
            headers = [str(c.value).strip() if c.value is not None else '' for c in cells]
            if not headers or len(set(headers)) != len(headers):
                raise ValueError('Missing or duplicate Excel headers')
            rows = []
            for cells in iterator:
                if all(c.value is None for c in cells):
                    raise ValueError('Empty Excel row; remove it or fill it explicitly')
                if any(c.data_type == 'f' for c in cells):
                    raise ValueError('Excel formulas require reviewed value-only export')
                rows.append(dict(zip(headers, [c.value for c in cells])))
                if len(rows) > config['max_rows']:
                    raise ValueError('Row limit exceeded')
            return headers, rows
        finally:
            workbook.close()
    raise ValueError('Supported formats: .csv, .xlsx, .pdf')

def normalize(headers, rows, config, branches):
    mapping = config['columns']
    if set(mapping) != set(FIELDS) or len(set(mapping.values())) != len(FIELDS):
        raise ValueError('Column mapping must map every canonical field exactly once')
    if not set(mapping.values()).issubset(headers):
        raise ValueError('Required columns missing: '+str(sorted(set(mapping.values())-set(headers))))
    if not rows:
        raise ValueError('Empty input cannot replace a published source')
    valid, errors, seen = [], [], set()
    for number, row in enumerate(rows, 2):
        try:
            r = {k:row.get(mapping[k]) for k in FIELDS}
            for k in ['branch_id','document_id','category','source']:
                if r[k] is None or not str(r[k]).strip():
                    raise ValueError('Missing '+k)
                r[k] = str(r[k]).strip()
            if r['branch_id'] not in branches or r['category'] not in CATEGORIES:
                raise ValueError('Unknown branch/category')
            d = r['recognized_date']
            if isinstance(d, datetime):
                if d.time().isoformat() != '00:00:00':
                    raise ValueError('Date must not include a time')
                d = d.date()
            if isinstance(d, date): d = d.isoformat()
            if date.fromisoformat(str(d)).isoformat() != str(d):
                raise ValueError('Date must be YYYY-MM-DD')
            r['recognized_date'] = str(d)
            r['amount_vnd'],r['line_number'] = integer(r['amount_vnd']),integer(r['line_number'])
            if not 0 < r['amount_vnd'] <= 9_000_000_000_000 or r['line_number'] <= 0:
                raise ValueError('Amount/line out of range')
            key = (r['branch_id'],r['document_id'],r['line_number'])
            if key in seen:
                raise ValueError('Duplicate document line within batch')
            seen.add(key)
            valid.append((number,r))
        except (ValueError,TypeError) as exc:
            errors.append({'row':number, 'error':str(exc)})
    return valid, errors

def publish_snapshot(conn, root):
    """Versioned snapshot + last atomic pointer; one SQLite read transaction."""
    snapshot_id = uuid.uuid4().hex
    folder = root/'gold'/snapshot_id
    folder.mkdir(parents=True)
    # Snapshot all tables consistently even if another writer commits later.
    conn.execute('BEGIN')
    try:
        fact = monthly_report(conn)
        branches = [dict(x) for x in conn.execute('SELECT * FROM branches ORDER BY id')]
        active = [dict(x) for x in conn.execute('SELECT * FROM pipeline_active ORDER BY source_id')]
    finally:
        conn.rollback()
    for row in fact: row['month_start'] = row['month']+'-01'
    months = [{'month_start':m+'-01','year':int(m[:4]),'month_number':int(m[5:])} for m in sorted({r['month'] for r in fact})]
    tables = {'fact_monthly_pnl':fact, 'dim_branch':branches, 'dim_month':months}
    for name, rows in tables.items():
        if not rows: continue
        with (folder/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    metadata = {'snapshot_id':snapshot_id, 'pipeline_version':VERSION, 'currency':'VND',
                'created_at':datetime.now().isoformat(), 'fact_rows':len(fact), 'active_sources':active,
                'basis':'recognized net entries; operating profit before depreciation, interest and tax'}
    atomic_json(folder/'manifest.json',metadata)
    atomic_json(root/'gold'/'current.json',{'snapshot_id':snapshot_id,'path':str(folder.resolve())})
    return folder

def run(path, root, source_id, config_path=None, replace=False, evidence_hash=None, reviewed_by=None):
    root = Path(root);path = Path(path)
    for part in ['bronze','silver','quarantine','gold']: (root/part).mkdir(parents=True,exist_ok=True)
    config = json.loads(Path(config_path or Path(__file__).with_name('config.json')).read_text())
    if config.get('schema_version') != 1: raise ValueError('Unsupported schema version')
    if not source_id.strip(): raise ValueError('source_id required')
    if path.stat().st_size > config['max_bytes']: raise ValueError('File too large')
    raw = path.read_bytes();digest = hashlib.sha256(raw).hexdigest()
    config_hash = hashlib.sha256(json.dumps({'config':config,'evidence_hash':evidence_hash,'reviewed_by':reviewed_by},sort_keys=True).encode()).hexdigest()
    run_id = uuid.uuid4().hex
    conn = connect(root/'state.sqlite3');initialize(conn);conn.executescript(SCHEMA)
    stage = 'bronze'
    try:
        with conn:
            conn.execute('INSERT INTO pipeline_runs(run_id,source_id,file_hash,config_hash,version,stage,status) VALUES (?,?,?,?,?,?,?)',(run_id,source_id,digest,config_hash,VERSION,stage,'running'))
        ext = path.suffix.lower()
        if ext not in ['.csv','.xlsx','.pdf']: raise ValueError('Unsupported extension')
        bronze = root/'bronze'/(digest+ext)
        if bronze.exists():
            if hashlib.sha256(bronze.read_bytes()).hexdigest()!=digest:
                raise ValueError('Bronze integrity check failed')
        else:
            with bronze.open('xb') as f: f.write(raw)
        with conn:
            conn.execute('INSERT OR IGNORE INTO bronze_files VALUES (?,?,?,?,?)',(digest,source_id,path.name,str(bronze),run_id))
        if ext == '.pdf':
            stage='extraction_review'
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(raw))
            if reader.is_encrypted: raise ValueError('Encrypted PDF requires reviewed decrypted source')
            if len(reader.pages)>100: raise ValueError('PDF exceeds 100 pages')
            texts = [page.extract_text() or '' for page in reader.pages]
            atomic_json(root/'silver'/(run_id+'.json'),{'file_hash':digest,'source_id':source_id,
                'pages':[{'page':i+1,'text':text} for i,text in enumerate(texts)],
                'requires_ocr':not any(t.strip() for t in texts), 'status':'review_required',
                'note':'Extracted text is not validated financial data. Create reviewed CSV/XLSX with evidence hash.'})
            with conn: conn.execute("UPDATE pipeline_runs SET stage=?,status='review_required',finished_at=CURRENT_TIMESTAMP WHERE run_id=?",(stage,run_id))
            return {'run_id':run_id,'status':'review_required','file_hash':digest,'gold_changed':False}
        active = conn.execute('SELECT * FROM pipeline_active WHERE source_id=?',(source_id,)).fetchone()
        if active and (active['file_hash'],active['config_hash'],active['version'])==(digest,config_hash,VERSION):
            with conn:conn.execute("UPDATE pipeline_runs SET status='skipped',stage='gold',finished_at=CURRENT_TIMESTAMP WHERE run_id=?",(run_id,))
            folder=publish_snapshot(conn,root)
            return {'run_id':run_id,'status':'skipped','gold':str(folder),'gold_changed':False}
        if active and not replace: raise ValueError('Source already active; explicit --replace required for revision')
        if evidence_hash:
            evidence = conn.execute('SELECT path FROM bronze_files WHERE file_hash=? AND source_id=?',(evidence_hash,source_id)).fetchone()
            if not evidence or not evidence['path'].endswith('.pdf') or not reviewed_by or not reviewed_by.strip():
                raise ValueError('PDF evidence must exist for same source_id and reviewer must be named')
        elif reviewed_by:
            raise ValueError('Reviewer provided without PDF evidence hash')
        stage='silver'
        headers,rows = read_records(raw,ext,config)
        valid,errors = normalize(headers,rows,config,{r['id'] for r in conn.execute('SELECT id FROM branches')})
        if errors:
            atomic_json(root/'quarantine'/(run_id+'.json'),{'run_id':run_id,'file_hash':digest,'errors':errors,'policy':'whole batch rejected'})
            raise ValueError(f'{len(errors)} invalid row(s); see quarantine/{run_id}.json')
        atomic_json(root/'silver'/(run_id+'.json'),{'run_id':run_id,'file_hash':digest,'rows':[{'source_row':n,**r} for n,r in valid]})
        stage='gold'
        with conn:
            # Acquire writer lock before checking revision state; prevent lost concurrent revisions.
            conn.execute('BEGIN IMMEDIATE')
            latest=conn.execute('SELECT run_id FROM pipeline_active WHERE source_id=?',(source_id,)).fetchone()
            if (latest['run_id'] if latest else None)!=(active['run_id'] if active else None):
                raise ValueError('Source changed during run; retry after reviewing latest version')
            if active:
                conn.execute('DELETE FROM entries WHERE id IN (SELECT entry_id FROM entry_lineage WHERE source_id=?)',(source_id,))
            for number,r in valid:
                record = [r[k] for k in FIELDS]
                # Original source retained in Silver; Gold points back to immutable Bronze.
                record[-1]='bronze:'+digest
                cur=conn.execute('INSERT INTO entries(branch_id,document_id,line_number,recognized_date,category,amount_vnd,source) VALUES (?,?,?,?,?,?,?)',record)
                conn.execute('INSERT INTO entry_lineage VALUES (?,?,?,?,?,?,?)',(cur.lastrowid,source_id,run_id,digest,number,evidence_hash,reviewed_by))
            conn.execute('INSERT OR REPLACE INTO pipeline_active VALUES (?,?,?,?,?)',(source_id,digest,config_hash,VERSION,run_id))
            conn.execute("UPDATE pipeline_runs SET stage='gold',status='succeeded',row_count=?,finished_at=CURRENT_TIMESTAMP WHERE run_id=?",(len(valid),run_id))
        stage='export'
        folder=publish_snapshot(conn,root)
        return {'run_id':run_id,'status':'succeeded','rows':len(valid),'gold':str(folder),'file_hash':digest}
    except Exception as exc:
        conn.rollback()
        status='export_failed' if stage=='export' else 'failed'
        with conn:conn.execute('UPDATE pipeline_runs SET stage=?,status=?,error=?,finished_at=CURRENT_TIMESTAMP WHERE run_id=?',(stage,status,str(exc),run_id))
        # Export failure means SQL already committed; retry same source to regenerate snapshot.
        raise
    finally:
        conn.close()

def main():
    p=argparse.ArgumentParser(description='Bếp Finance medallion reference pipeline')
    p.add_argument('file');p.add_argument('--root',default='backend/data/lakehouse')
    p.add_argument('--source-id',required=True);p.add_argument('--config');p.add_argument('--replace',action='store_true')
    p.add_argument('--evidence-hash');p.add_argument('--reviewed-by')
    args=p.parse_args()
    result=run(args.file,args.root,args.source_id,args.config,args.replace,args.evidence_hash,args.reviewed_by)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
