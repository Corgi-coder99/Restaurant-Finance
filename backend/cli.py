from contextlib import closing
import argparse
import json
from pathlib import Path
from backend.analytics import connect, initialize, import_csv, monthly_report, forecast
from backend.data_quality import review_period

def main():
    parser = argparse.ArgumentParser(description='Bếp Finance: SQL + Python analytics')
    parser.add_argument('--db',default='backend/data/finance.sqlite3')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('init')
    p=commands.add_parser('import');p.add_argument('csv')
    p=commands.add_parser('report');p.add_argument('--branch')
    p=commands.add_parser('forecast');p.add_argument('--branch',required=True);p.add_argument('--horizon',type=int,default=3);p.add_argument('--as-of')
    p=commands.add_parser('review-period');p.add_argument('--branch',required=True);p.add_argument('--month',required=True);p.add_argument('--status',choices=['complete','zero'],required=True);p.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    with closing(connect(args.db)) as conn, conn:
        initialize(conn)
        if args.command=='init': result={'status':'initialized'}
        elif args.command=='import': result={'rows_imported':import_csv(conn,args.csv)}
        elif args.command=='report': result=monthly_report(conn,args.branch)
        elif args.command=='review-period':result=review_period(conn,args.branch,args.month,args.status,args.reviewer)
        else: result=forecast(conn,args.branch,args.horizon,args.as_of)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__': main()
