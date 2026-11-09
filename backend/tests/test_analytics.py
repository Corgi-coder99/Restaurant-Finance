import csv
import tempfile
import unittest
from pathlib import Path
import asyncio
import os,json
from unittest.mock import patch
from backend.data_quality import review_period
import httpx
from backend.analytics import connect,initialize,import_csv,monthly_report,forecast,ROOT
from backend import api

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'BEP_AUDIT_KEY':'test-audit-key-not-for-production-0123456789','BEP_ERP_USERS':json.dumps({'test-owner':{'name':'Owner','role':'owner','branches':['q1']}})});self.env.start()
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.conn=connect(self.path);initialize(self.conn)
    def tearDown(self):
        self.conn.close();self.tmp.cleanup();self.env.stop()
    def test_report_reconciliation_and_duplicate_rollback(self):
        count=import_csv(self.conn,ROOT/'data/sample_entries.csv')
        report=monthly_report(self.conn,'q1')
        self.assertEqual(len(report),24)
        for row in report:
            self.assertEqual(row['operating_profit_vnd'],row['revenue_vnd']-row['total_cost_vnd'])
            self.assertGreater(row['rent_vnd'],0)
        with self.assertRaises(ValueError): import_csv(self.conn,ROOT/'data/sample_entries.csv')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM entries').fetchone()[0],count)
    def test_seasonal_forecast_and_backtest(self):
        import_csv(self.conn,ROOT/'data/sample_entries.csv')
        for row in monthly_report(self.conn,'q1'):review_period(self.conn,'q1',row['month'],'complete','Test reviewer')
        result=forecast(self.conn,'q1',3,'2026-01-01')
        self.assertEqual(result['forecast'][0]['month'],'2026-01')
        self.assertEqual(result['method'],'validated_component_selection')
        self.assertEqual(result['backtest']['test_months'],3)
        self.conn.execute("DELETE FROM entries WHERE recognized_date='2025-05-01'")
        with self.assertRaises(ValueError): forecast(self.conn,'q1',3,'2026-01-01')
    def test_invalid_row_rejects_entire_file(self):
        path=Path(self.tmp.name)/'bad.csv'
        with open(ROOT/'data/sample_entries.csv',newline='') as f: rows=list(csv.reader(f))[:3]
        rows[-1][5]='-1'
        with open(path,'w',newline='') as f: csv.writer(f).writerows(rows)
        with self.assertRaises(ValueError): import_csv(self.conn,path)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM entries').fetchone()[0],0)
    def test_parameterized_branch_and_api(self):
        import_csv(self.conn,ROOT/'data/sample_entries.csv')
        with self.assertRaises(ValueError):monthly_report(self.conn,"q1' OR 1=1 --")
        for row in monthly_report(self.conn,'q1'):review_period(self.conn,'q1',row['month'],'complete','API sample reviewer')
        old=api.DB;api.DB=self.path
        try:
            async def check_api():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),base_url='http://test',headers={'Authorization':'Bearer test-owner'}) as client:
                    self.assertEqual(len((await client.get('/api/reports/monthly?branch=q1')).json()['rows']),24)
                    self.assertEqual((await client.get('/api/forecast?branch=q1')).status_code,422)
                    self.assertEqual((await client.get('/api/forecast?branch=unknown')).status_code,403)
                    self.assertEqual((await client.get('/api/forecast?branch=q1&horizon=9')).status_code,422)
            asyncio.run(check_api())
        finally: api.DB=old

if __name__=='__main__':unittest.main()
