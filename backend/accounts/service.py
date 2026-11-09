"""Local password identities, signed authorization records and expiring email recovery."""
import hashlib,hmac,json,os,re,secrets,smtplib,sqlite3,ssl,time,logging
from contextlib import closing
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit
from backend.integrity import key_from_env,sign,verify,canonical

class AuthError(ValueError):pass
class Accounts:
 def __init__(self,path=None,clock=time.time,mailer=None):
  self.path=Path(path or os.environ.get('BEP_AUTH_DATABASE','backend/data/accounts.sqlite3'));self.path.parent.mkdir(parents=True,exist_ok=True)
  self.key=key_from_env();self.clock=clock;self.mailer=mailer or self.send_email
  with self.db() as c:c.executescript('''
   CREATE TABLE IF NOT EXISTS accounts(email TEXT PRIMARY KEY,payload TEXT NOT NULL,signature TEXT NOT NULL,password TEXT NOT NULL,version INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,email TEXT NOT NULL,version INTEGER NOT NULL,expires INTEGER NOT NULL,signature TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS resets(digest TEXT PRIMARY KEY,email TEXT NOT NULL,version INTEGER NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,signature TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS attempts(subject TEXT NOT NULL,at INTEGER NOT NULL);
   CREATE INDEX IF NOT EXISTS attempts_subject ON attempts(subject,at);
  ''')
 def db(self):
  c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return closing(c)
 def digest(self,text):return hmac.new(self.key,text.encode(),hashlib.sha256).hexdigest()
 @staticmethod
 def email(value):
  if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise AuthError('Invalid email')
  return value.strip().lower()
 @staticmethod
 def password(value):
  if not isinstance(value,str) or not 12<=len(value)<=128:raise AuthError('Password must contain 12–128 characters')
  salt=secrets.token_bytes(16);digest=hashlib.scrypt(value.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
  return salt.hex()+':'+digest.hex()
 @staticmethod
 def matches(value,stored):
  if not isinstance(value,str) or len(value)>128:return False
  salt,expected=stored.split(':');actual=hashlib.scrypt(value.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32)
  return hmac.compare_digest(actual.hex(),expected)
 def record(self,c,email):
  row=c.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
  if not row:return None
  verify(self.key,{'email':row['email'],'payload':row['payload'],'password':row['password'],'version':row['version']},row['signature'])
  return row
 def save(self,c,email,identity,password,version):
  payload=canonical(identity);signature=sign(self.key,{'email':email,'payload':payload,'password':password,'version':version})
  c.execute('INSERT OR REPLACE INTO accounts VALUES(?,?,?,?,?)',(email,payload,signature,password,version))
 def create(self,actor,body):
  if actor['role'] not in ('owner','manager'):raise PermissionError('Account administration requires manager or owner')
  if set(body)-{'email','password','name','role','branches','employee_id'}:raise AuthError('Unsupported account fields')
  email=self.email(body.get('email'));role=body.get('role');branches=body.get('branches')
  if role not in ('owner','manager','cashier'):raise AuthError('Invalid account role')
  if actor['role']=='manager' and role!='cashier':raise PermissionError('Managers may only create cashier accounts')
  if not isinstance(branches,list) or not branches or any(not isinstance(b,str) or b not in actor['branches'] for b in branches):raise PermissionError('Account branches exceed administrator scope')
  if not isinstance(body.get('name'),str) or not 1<=len(body['name'])<=120:raise AuthError('Account name required')
  if role=='cashier' and (not isinstance(body.get('employee_id'),str) or not body['employee_id']):raise AuthError('Cashier employee link required')
  password=self.password(body.get('password'));identity={'user_id':secrets.token_hex(16),'name':body['name'],'role':role,'branches':sorted(set(branches)),'email':email,'enabled':True}
  if body.get('employee_id'):identity['employee_id']=body['employee_id']
  with self.db() as c,c:
   c.execute('BEGIN IMMEDIATE')
   if self.record(c,email):raise AuthError('Account already exists')
   self.save(c,email,identity,password,1)
  return {'email':email,'role':role,'branches':identity['branches']}
 def throttle(self,subject,maximum,window):
  now=int(self.clock())
  with self.db() as c,c:
   c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM attempts WHERE at<?',(now-3600,))
   if c.execute('SELECT COUNT(*) FROM attempts WHERE subject=? AND at>?',(subject,now-window)).fetchone()[0]>=maximum:raise AuthError('Too many attempts; try later')
   c.execute('INSERT INTO attempts VALUES(?,?)',(subject,now))
 def login(self,email,password,role):
  email=self.email(email);self.throttle('login:'+self.digest(email),8,900)
  with self.db() as c,c:
   row=self.record(c,email)
   # Same expensive derivation for unknown emails.
   stored=row['password'] if row else ('00'*16+':'+'00'*32)
   valid=self.matches(password,stored);identity=json.loads(row['payload']) if row else None
   if not valid or not identity or not identity['enabled'] or identity['role']!=role:raise AuthError('Invalid credentials')
   token=secrets.token_urlsafe(32);record={'digest':self.digest(token),'email':email,'version':row['version'],'expires':int(self.clock())+8*3600};c.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(*record.values(),sign(self.key,record)))
  return token,identity
 def resolve(self,token):
  if not token:return None
  with self.db() as c:
   s=c.execute('SELECT * FROM sessions WHERE digest=?',(self.digest(token),)).fetchone()
   if not s:return None
   record=dict(s);signature=record.pop('signature');verify(self.key,record,signature)
   if s['expires']<=self.clock():return None
   row=self.record(c,s['email'])
   if not row or row['version']!=s['version']:return None
   identity=json.loads(row['payload']);return identity if identity['enabled'] else None
 def logout(self,token):
  with self.db() as c,c:c.execute('DELETE FROM sessions WHERE digest=?',(self.digest(token),))
 def change(self,identity,old,new):
  if not identity.get('email'):raise AuthError('Password account required')
  hashed=self.password(new)
  with self.db() as c,c:
   c.execute('BEGIN IMMEDIATE');row=self.record(c,identity['email'])
   if not row or not self.matches(old,row['password']):raise AuthError('Invalid credentials')
   self.save(c,row['email'],json.loads(row['payload']),hashed,row['version']+1)
   c.execute('DELETE FROM sessions WHERE email=?',(row['email'],))
 def recovery(self,email):
  email=self.email(email);self.throttle('reset:'+self.digest(email),3,3600)
  # Fail clearly for missing server delivery configuration, regardless of email existence.
  if not os.environ.get('BEP_PUBLIC_URL') or (self.mailer==self.send_email and not os.environ.get('BEP_SMTP_HOST')):raise AuthError('Email recovery is not configured')
  base=os.environ['BEP_PUBLIC_URL'].rstrip('/');parsed=urlsplit(base)
  if parsed.scheme!='https' or not parsed.netloc or parsed.query or parsed.fragment:raise AuthError('Recovery URL must use HTTPS')
  with self.db() as c,c:
   c.execute('BEGIN IMMEDIATE');row=self.record(c,email)
   if not row:return
   token=secrets.token_urlsafe(32);digest=self.digest(token)
   c.execute('UPDATE resets SET used=1 WHERE email=?',(email,))
   record={'digest':digest,'email':email,'version':row['version'],'expires':int(self.clock())+900};c.execute('INSERT INTO resets VALUES(?,?,?,?,0,?)',(*record.values(),sign(self.key,record)))
  try:self.mailer(email,base+'/workspace/#reset='+token)
  except Exception:
   with self.db() as c,c:c.execute('UPDATE resets SET used=1 WHERE digest=?',(digest,))
   logging.getLogger(__name__).error('Recovery delivery failed; verify SMTP configuration')
 def reset(self,token,password):
  if not isinstance(token,str) or not 20<=len(token)<=200:raise AuthError('Invalid recovery link')
  hashed=self.password(password)
  with self.db() as c,c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM resets WHERE digest=?',(self.digest(token),)).fetchone()
   if r:
    record={k:r[k] for k in ('digest','email','version','expires')};verify(self.key,record,r['signature'])
   row=self.record(c,r['email']) if r else None
   if not r or r['used'] or r['expires']<=self.clock() or not row or r['version']!=row['version']:raise AuthError('Invalid recovery link')
   self.save(c,row['email'],json.loads(row['payload']),hashed,row['version']+1)
   c.execute('UPDATE resets SET used=1 WHERE email=?',(row['email'],));c.execute('DELETE FROM sessions WHERE email=?',(row['email'],))
 @staticmethod
 def send_email(email,url):
  host=os.environ['BEP_SMTP_HOST'];username=os.environ.get('BEP_SMTP_USER');password=os.environ.get('BEP_SMTP_PASSWORD');sender=os.environ.get('BEP_SMTP_FROM',username)
  if not username or not password or not sender:raise AuthError('SMTP credentials required')
  msg=EmailMessage();msg['From']=sender;msg['To']=email;msg['Subject']='Bep Finance — password recovery'
  msg.set_content('Reset your Bep Finance password within 15 minutes:\n'+url+'\n\nIf you did not request this, ignore this email.\n')
  with smtplib.SMTP_SSL(host,int(os.environ.get('BEP_SMTP_PORT','465')),context=ssl.create_default_context(),timeout=15) as smtp:smtp.login(username,password);smtp.send_message(msg)
