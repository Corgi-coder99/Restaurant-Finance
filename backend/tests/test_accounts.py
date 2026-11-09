import asyncio,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend.accounts.service import Accounts,AuthError
from backend.integrity import IntegrityError
from backend.api import app

class AccountTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=[1000000];self.mail=[]
  self.env=patch.dict(os.environ,{'BEP_AUDIT_KEY':'test-only-key-not-production-1234567890','BEP_AUTH_DATABASE':str(Path(self.tmp.name)/'auth.sqlite3'),'BEP_PUBLIC_URL':'https://restaurant.example','BEP_COOKIE_SECURE':'false','BEP_ERP_USERS':json.dumps({'bootstrap-token':{'name':'Bootstrap','role':'owner','branches':['q1']}})});self.env.start()
  self.a=Accounts(clock=lambda:self.now[0],mailer=lambda email,url:self.mail.append((email,url)))
  self.owner={'role':'owner','branches':['q1'],'user_id':'owner'}
  self.body={'email':'owner@example.com','password':'a-long-test-password','name':'Owner','role':'owner','branches':['q1']};self.a.create(self.owner,self.body)
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_password_hash_role_and_session_revocation(self):
  with self.assertRaises(AuthError):self.a.login(self.body['email'],self.body['password'],'manager')
  token,identity=self.a.login(self.body['email'],self.body['password'],'owner');self.assertEqual(self.a.resolve(token)['role'],'owner')
  with self.a.db() as c:self.assertNotIn(self.body['password'],c.execute('SELECT password FROM accounts').fetchone()[0])
  self.a.change(identity,self.body['password'],'a-new-strong-password');self.assertIsNone(self.a.resolve(token))
  with self.assertRaises(AuthError):self.a.login(self.body['email'],self.body['password'],'owner')
 def test_recovery_one_time_expiring_and_old_sessions_revoked(self):
  token,_=self.a.login(self.body['email'],self.body['password'],'owner');self.a.recovery(self.body['email']);reset=self.mail[-1][1].split('#reset=')[1]
  self.a.reset(reset,'reset-strong-password');self.assertIsNone(self.a.resolve(token))
  with self.assertRaises(AuthError):self.a.reset(reset,'another-strong-password')
  self.a.recovery(self.body['email']);expired=self.mail[-1][1].split('#reset=')[1];self.now[0]+=901
  with self.assertRaises(AuthError):self.a.reset(expired,'another-strong-password')
 def test_reset_unknown_email_generic_and_authorization_scope(self):
  self.a.recovery('unknown@example.com');self.assertEqual(self.mail,[])
  manager={'role':'manager','branches':['q1']}
  with self.assertRaises(PermissionError):self.a.create(manager,{**self.body,'email':'new@example.com'})
  with self.assertRaises(PermissionError):self.a.create(manager,{**self.body,'email':'new@example.com','role':'cashier','employee_id':'e1','branches':['td']})
  with self.assertRaises(PermissionError):self.a.create({'role':'cashier','branches':['q1']},self.body)
 def test_tampered_account_and_session_blocked(self):
  token,_=self.a.login(self.body['email'],self.body['password'],'owner')
  with self.a.db() as c,c:c.execute('UPDATE sessions SET email=?',('other@example.com',))
  with self.assertRaises(IntegrityError):self.a.resolve(token)
  with self.a.db() as c,c:c.execute('UPDATE accounts SET version=99')
  with self.assertRaises(IntegrityError):self.a.login(self.body['email'],self.body['password'],'owner')
 def test_delivery_failure_does_not_expose_account_or_leave_valid_reset(self):
  def fail(email,url):raise RuntimeError('SMTP unavailable')
  self.a.mailer=fail
  with self.assertLogs('backend.accounts.service',level='ERROR'):self.a.recovery(self.body['email'])
  with self.a.db() as c:self.assertEqual(c.execute('SELECT used FROM resets').fetchone()[0],1)
 def test_login_throttle(self):
  for _ in range(8):
   with self.assertRaises(AuthError):self.a.login(self.body['email'],'wrong-password','owner')
  with self.assertRaisesRegex(AuthError,'Too many'):self.a.login(self.body['email'],self.body['password'],'owner')
 def test_cookie_flow_and_origin_required(self):
  # Service-injected test clock is not used by HTTP accounts; recreate via API admin.
  async def run():
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
    r=await c.post('/api/auth/accounts',headers={'Authorization':'Bearer bootstrap-token'},json={**self.body,'email':'http@example.com'});self.assertEqual(r.status_code,200)
    r=await c.post('/api/auth/login',json={'email':'http@example.com','password':self.body['password'],'role':'owner'});self.assertEqual(r.status_code,200);self.assertIn('httponly',r.headers['set-cookie'].lower());self.assertIn('samesite=strict',r.headers['set-cookie'].lower())
    r=await c.get('/api/auth/me');self.assertEqual(r.json()['identity']['role'],'owner')
    r=await c.post('/api/auth/password',json={'current_password':self.body['password'],'new_password':'another-test-password'});self.assertEqual(r.status_code,403)
    r=await c.post('/api/auth/password',headers={'Origin':'http://test'},json={'current_password':self.body['password'],'new_password':'another-test-password'});self.assertEqual(r.status_code,200)
    self.assertEqual((await c.get('/api/auth/me')).status_code,401)
  asyncio.run(run())
