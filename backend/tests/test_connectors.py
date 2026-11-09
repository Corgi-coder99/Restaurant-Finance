import csv
import json
import tempfile
import unittest
from pathlib import Path
from backend.connectors.pos_staging import stage,preview,reconcile,money,FIELDS

class ConnectorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.lake=self.root/'staging'
  self.config=self.root/'config.json'
  self.config.write_text(json.dumps({'schema_version':1,'provider':'laddition_suite','company_id':'demo',
   'sheet':'pos_closes','max_bytes':100000,'max_rows':100,'decimal_separator':',','closed_status':'closed',
   'restaurants':{'DEMO':'q1'},'columns':{x:x for x in FIELDS}}))
  self.rows=[['DEMO','Z1','2026-10-01','EUR','1000,00','100,00','1100,00','closed']]
 def tearDown(self):self.tmp.cleanup()
 def file(self):
  p=self.root/'data.csv'
  with p.open('w',newline='') as f:
   w=csv.writer(f);w.writerow(FIELDS);w.writerows(self.rows)
  return p
 def test_money_precision(self):
  self.assertEqual(money('1234,56','EUR',','),123456)
  self.assertEqual(money('-5,00','EUR',','),-500)
  with self.assertRaises(ValueError):money('1234,567','EUR',',')
  with self.assertRaises(ValueError):money('1.234,56','EUR',',')
 def test_idempotent_and_no_gold(self):
  result=stage(self.file(),self.lake,self.config,'october')
  self.assertFalse(result['gold_changed']);self.assertEqual(result['rows'],1)
  self.assertEqual(stage(self.file(),self.lake,self.config,'october')['status'],'skipped')
  self.assertEqual(preview(self.lake)[0]['net_minor'],100000)
 def test_revision_and_rollback(self):
  stage(self.file(),self.lake,self.config,'october')
  self.rows[0][4:7]=['2000,00','200,00','2200,00']
  with self.assertRaisesRegex(ValueError,'replace'):stage(self.file(),self.lake,self.config,'october')
  stage(self.file(),self.lake,self.config,'october',True)
  self.assertEqual(preview(self.lake)[0]['net_minor'],200000)
  self.rows[0][6]='1,00'
  with self.assertRaises(ValueError):stage(self.file(),self.lake,self.config,'october',True)
  self.assertEqual(preview(self.lake)[0]['net_minor'],200000)
 def test_different_currency_never_combined(self):
  self.rows.append(['DEMO','Z2','2026-10-02','VND','1000000','100000','1100000','closed'])
  stage(self.file(),self.lake,self.config,'october')
  self.assertEqual({r['currency'] for r in preview(self.lake)},{'EUR','VND'})
  self.assertEqual(len(preview(self.lake)),2)
 def test_reconcile_never_sums_pos_and_ledger(self):
  rows=[{'branch_id':'q1','month':'2026-10','currency':'EUR','net_minor':100000}]
  self.assertEqual(reconcile(rows,rows)[0]['delta_minor'],0)
  other=[{**rows[0],'net_minor':99000}]
  result=reconcile(rows,other)[0]
  self.assertEqual(result['delta_minor'],1000);self.assertEqual(result['status'],'review_required')
  self.assertEqual(reconcile(rows,[])[0]['status'],'missing_source')
 def test_duplicate_across_batches_rejected(self):
  stage(self.file(),self.lake,self.config,'october')
  with self.assertRaises(Exception):stage(self.file(),self.lake,self.config,'different-batch')
  self.assertEqual(preview(self.lake)[0]['closes'],1)

if __name__=='__main__':unittest.main()
