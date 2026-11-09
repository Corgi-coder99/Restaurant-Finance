from contextlib import closing
import argparse
import json
import sqlite3
from pathlib import Path
from backend.erp.service import ERP
from backend.erp.audit import seal_legacy,verify_ledger


def main():
    p=argparse.ArgumentParser(description='Bếp restaurant operations MVP, one company/ledger')
    p.add_argument('--db',default='backend/data/erp.sqlite3');p.add_argument('--currency',default='GBP');p.add_argument('--jurisdiction',default='GB')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    r=sub.add_parser('report');r.add_argument('--branch',default='q1');r.add_argument('--start',default='0001-01-01');r.add_argument('--end',default='9999-12-31')
    post=sub.add_parser('post');post.add_argument('json_file');post.add_argument('--key',required=True);post.add_argument('--actor',default='local-owner')
    legacy=sub.add_parser('seal-legacy');legacy.add_argument('--reviewer',required=True);legacy.add_argument('--reason',required=True)
    backup=sub.add_parser('backup');backup.add_argument('output')
    args=p.parse_args();erp=ERP(args.db,args.currency,args.jurisdiction)
    if args.command=='init':result={'status':'initialized','currency':args.currency,'jurisdiction':args.jurisdiction}
    elif args.command=='report':result=erp.report(args.branch,args.start,args.end)
    elif args.command=='seal-legacy':
        with closing(erp.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE');result=seal_legacy(conn,erp.audit_key,args.reviewer,args.reason)
    elif args.command=='post':result=erp.post(json.loads(Path(args.json_file).read_text()),args.key,args.actor)
    else:
        target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        # Fail if target exists; never overwrite a previous backup.
        with target.open('xb'):pass
        source=erp.connect();dest=sqlite3.connect(target)
        try:
            source.execute('BEGIN');verify_ledger(source,erp.audit_key);source.backup(dest)
        finally:dest.close();source.close()
        result={'status':'backed_up','path':str(target)}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
