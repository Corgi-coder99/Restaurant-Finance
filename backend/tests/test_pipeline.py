from contextlib import closing
import csv
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from openpyxl import Workbook
from pypdf import PdfWriter
from backend.analytics import connect, monthly_report
from backend.pipeline.runner import run, FIELDS

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.lake=self.root/'lake'
        self.rows=[['q1','TEST',1,'2026-10-01','revenue',100000000,'test'],
                   ['q1','TEST',2,'2026-10-01','rent',10000000,'test']]
    def tearDown(self):self.tmp.cleanup()
    def csv(self,name='input.csv',rows=None):
        p=self.root/name
        with p.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(FIELDS);w.writerows(self.rows if rows is None else rows)
        return p
    def profit(self):
        with closing(connect(self.lake/'state.sqlite3')) as c, c:return monthly_report(c,'q1')[0]['operating_profit_vnd']
    def test_rerun_does_not_duplicate_and_exports_star(self):
        p=self.csv();result=run(p,self.lake,'one');self.assertEqual(result['rows'],2)
        self.assertEqual(self.profit(),90000000)
        self.assertEqual(run(p,self.lake,'one')['status'],'skipped')
        manifest=json.loads((self.lake/'gold/current.json').read_text())
        folder=Path(manifest['path'])
        self.assertTrue((folder/'fact_monthly_pnl.csv').exists())
        self.assertTrue((folder/'dim_month.csv').exists())
        with closing(connect(self.lake/'state.sqlite3')) as c, c:
            self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],2)
    def test_revision_requires_flag_and_replaces_atomically(self):
        p=self.csv();run(p,self.lake,'one')
        self.rows[1][5]=20000000;p=self.csv()
        with self.assertRaisesRegex(ValueError,'replace'):run(p,self.lake,'one')
        self.assertEqual(self.profit(),90000000)
        run(p,self.lake,'one',replace=True);self.assertEqual(self.profit(),80000000)
        self.rows[1][5]='10,000';p=self.csv()
        with self.assertRaises(ValueError):run(p,self.lake,'one',replace=True)
        self.assertEqual(self.profit(),80000000)
        self.assertEqual(len(list((self.lake/'quarantine').glob('*.json'))),1)
    def test_conflict_rolls_back_replaced_rows(self):
        run(self.csv(),self.lake,'one')
        run(self.csv('other.csv',[['q1','OTHER',1,'2026-10-01','other',1000000,'test']]),self.lake,'two')
        conflict=self.csv('revision.csv',[['q1','OTHER',1,'2026-10-01','rent',20000000,'test']])
        with self.assertRaises(Exception):run(conflict,self.lake,'one',replace=True)
        self.assertEqual(self.profit(),89000000)
    def test_excel_and_formula_rejection(self):
        p=self.root/'test.xlsx';w=Workbook();s=w.active;s.title='entries';s.append(FIELDS)
        for row in self.rows:s.append(row)
        w.save(p);run(p,self.lake,'excel');self.assertEqual(self.profit(),90000000)
        s['F2']='=100+200';w.save(p)
        with self.assertRaisesRegex(ValueError,'formulas'):run(p,self.lake,'excel',replace=True)
        self.assertEqual(self.profit(),90000000)
    def test_pdf_never_auto_posts_requires_reviewed_evidence(self):
        p=self.root/'scan.pdf';w=PdfWriter();w.add_blank_page(width=300,height=200)
        with p.open('wb') as f:w.write(f)
        result=run(p,self.lake,'pdf-one');self.assertEqual(result['status'],'review_required')
        with closing(connect(self.lake/'state.sqlite3')) as c, c:self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],0)
        with self.assertRaisesRegex(ValueError,'reviewer'):run(self.csv(),self.lake,'pdf-one',evidence_hash=result['file_hash'])
        run(self.csv(),self.lake,'pdf-one',evidence_hash=result['file_hash'],reviewed_by='Reviewer demo')
        self.assertEqual(self.profit(),90000000)
    def test_export_failure_can_recover_without_duplicate_sql(self):
        p=self.csv()
        with patch('backend.pipeline.runner.publish_snapshot',side_effect=OSError('temporary disk error')):
            with self.assertRaises(OSError):run(p,self.lake,'one')
        self.assertEqual(self.profit(),90000000)
        with closing(connect(self.lake/'state.sqlite3')) as c, c:
            self.assertEqual(c.execute('SELECT status FROM pipeline_runs').fetchone()[0],'export_failed')
        result=run(p,self.lake,'one')
        self.assertEqual(result['status'],'skipped')
        self.assertTrue((Path(result['gold'])/'manifest.json').exists())
        with closing(connect(self.lake/'state.sqlite3')) as c, c:
            self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],2)

    def test_missing_columns_and_unknown_branch_fail(self):
        self.rows[0][0]='unknown'
        with self.assertRaises(ValueError):run(self.csv(),self.lake,'bad')
        with closing(connect(self.lake/'state.sqlite3')) as c, c:
            self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],0)
            row=c.execute('SELECT status,stage FROM pipeline_runs').fetchone()
            self.assertEqual(tuple(row),('failed','silver'))

if __name__=='__main__':unittest.main()
