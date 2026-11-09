from backend.integrity import sign,verify,IntegrityError


def master_snapshot(c):
    return {table:[dict(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY '+order)] for table,order in [
        ('erp_meta','key'),('erp_accounts','code'),('erp_branches','id'),('erp_products','id'),('erp_items','id'),('erp_recipes','product_id,item_id')]}

def document_snapshot(c,doc):
    record=c.execute('SELECT * FROM erp_documents WHERE id=?',(doc,)).fetchone()
    if not record:raise IntegrityError('Signed document is missing')
    data={'document':dict(record)}
    for table,field,order in [('erp_lines','document_id','id'),('erp_stock_moves','document_id','id'),
        ('erp_settlements','document_id','document_id'),('erp_assets','document_id','id'),('erp_depreciation','document_id','asset_id,month')]:
        data[table]=[dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE '+field+'=? ORDER BY '+order,(doc,))]
    return data

def initialize_baseline(c,key):
    if not c.execute('SELECT 1 FROM erp_integrity_genesis').fetchone() and not c.execute('SELECT 1 FROM erp_documents').fetchone():
        c.execute('INSERT INTO erp_integrity_genesis VALUES(1,?)',(sign(key,master_snapshot(c)),))

def append(c,key,doc):
    previous=c.execute('SELECT seq,signature FROM erp_integrity ORDER BY seq DESC LIMIT 1').fetchone()
    seq=previous[0]+1 if previous else 1
    anchor=previous[1] if previous else c.execute('SELECT signature FROM erp_integrity_genesis WHERE id=1').fetchone()[0]
    value={'seq':seq,'previous_signature':anchor,'data':document_snapshot(c,doc)}
    c.execute('INSERT INTO erp_integrity VALUES(?,?,?,?)',(seq,doc,anchor,sign(key,value)))

def verify_ledger(c,key):
    genesis=c.execute('SELECT signature FROM erp_integrity_genesis WHERE id=1').fetchone()
    if not genesis:raise IntegrityError('Unsigned legacy ledger: review and migrate before processing; never auto-trust old data')
    verify(key,master_snapshot(c),genesis[0]);previous=genesis[0];signed=[]
    for expected,row in enumerate(c.execute('SELECT * FROM erp_integrity ORDER BY seq').fetchall(),1):
        if row['seq']!=expected or row['previous_signature']!=previous:raise IntegrityError('Audit chain link missing')
        data=document_snapshot(c,row['document_id'])
        verify(key,{'seq':expected,'previous_signature':previous,'data':data},row['signature'])
        if sum(r['debit']-r['credit'] for r in data['erp_lines']):raise IntegrityError('Unbalanced signed document')
        previous=row['signature'];signed.append(row['document_id'])
    if set(signed)!={r[0] for r in c.execute('SELECT id FROM erp_documents')}:raise IntegrityError('Unsigned or missing financial documents')
    expected={(r[0],r[1]):(r[2],r[3]) for r in c.execute('SELECT d.branch_id,m.item_id,SUM(m.quantity),SUM(m.value_minor) FROM erp_stock_moves m JOIN erp_documents d ON d.id=m.document_id GROUP BY d.branch_id,m.item_id') if r[2] or r[3]}
    actual={(r['branch_id'],r['item_id']):(r['quantity'],r['value_minor']) for r in c.execute('SELECT * FROM erp_stock') if r['quantity'] or r['value_minor']}
    if actual!=expected:raise IntegrityError('Materialized stock does not reconcile to signed movements')
    locked={(r[0],r[1],r[2]) for r in c.execute("SELECT branch_id,substr(business_date,1,7),actor FROM erp_documents WHERE kind='close_period'")}
    if locked!={(r['branch_id'],r['month'],r['closed_by']) for r in c.execute('SELECT * FROM erp_periods')}:raise IntegrityError('Period lock state changed')
    return {'verified':True,'signed_documents':len(signed),'checks':['master_data_hmac','document_hmac_chain','journal_balance','stock_reconciliation','period_locks'],
        'limits':'Does not detect rollback to an earlier valid full database snapshot; use separately protected external anchors and backups.'}

def seal_legacy(c,key,reviewer,reason):
    """Operator-only migration. Signs reviewed current state, not historical truth."""
    from datetime import datetime,timezone
    from backend.integrity import canonical
    if not reviewer.strip() or not reason.strip():raise IntegrityError('Reviewer and reconciliation reason required')
    if c.execute('SELECT 1 FROM erp_integrity_genesis').fetchone() or c.execute('SELECT 1 FROM erp_integrity').fetchone():raise IntegrityError('Existing integrity baseline cannot be reset')
    docs=c.execute('SELECT id FROM erp_documents ORDER BY rowid').fetchall()
    if not docs:raise IntegrityError('No legacy documents to migrate')
    for doc in docs:
        record=document_snapshot(c,doc[0])
        if sum(r['debit']-r['credit'] for r in record['erp_lines']):raise IntegrityError('Legacy document is unbalanced; reconcile first')
    c.execute('INSERT INTO erp_meta VALUES(?,?)',('integrity_migration_review',canonical({'reviewer':reviewer,'reason':reason,'at':datetime.now(timezone.utc).isoformat()})))
    c.execute('INSERT INTO erp_integrity_genesis VALUES(1,?)',(sign(key,master_snapshot(c)),))
    for doc in docs:append(c,key,doc[0])
    return verify_ledger(c,key)
