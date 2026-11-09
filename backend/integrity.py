"""HMAC tamper evidence. The key must live outside the database and source code."""
import hashlib
import hmac
import json
import os

class IntegrityError(ValueError):pass

def key_from_env():
    value=os.environ.get('BEP_AUDIT_KEY','')
    if len(value)<32:raise IntegrityError('Configure BEP_AUDIT_KEY with at least 32 characters outside the database')
    return value.encode()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sign(key,value):return hmac.new(key,canonical(value).encode(),hashlib.sha256).hexdigest()
def verify(key,value,signature):
    if not hmac.compare_digest(sign(key,value),signature):raise IntegrityError('Signed data changed; stop processing and investigate')
