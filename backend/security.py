"""Shared, fail-closed API identity and branch scope enforcement."""
import json
import os
import secrets
from datetime import datetime,timezone
from fastapi import Header,HTTPException,Request

async def user(request: Request,authorization: str=Header(default='')):
    if not authorization and request.cookies.get('bep_session'):
        from backend.accounts.service import Accounts
        identity=Accounts().resolve(request.cookies['bep_session'])
        if identity:return identity
        raise HTTPException(401,'Session expired')
    try:
        users=json.loads(os.environ.get('BEP_ERP_USERS','{}'))
        if not isinstance(users,dict):raise ValueError()
    except (json.JSONDecodeError,ValueError):raise HTTPException(503,'Invalid server credential configuration')
    if not users:raise HTTPException(503,'Configure BEP_ERP_USERS on the backend first')
    token=authorization[7:] if authorization.startswith('Bearer ') else ''
    for key,identity in users.items():
        if not isinstance(identity,dict):continue
        if token and secrets.compare_digest(token.encode(),key.encode()):
            if identity.get('enabled',True) is not True or identity.get('role') not in ('owner','manager','accountant','cashier'):
                raise HTTPException(401,'Access token is disabled')
            if identity.get('expires_at'):
                try:
                    expires=datetime.fromisoformat(identity['expires_at'].replace('Z','+00:00'))
                    if expires.tzinfo is None:raise ValueError()
                except (ValueError,TypeError,AttributeError):raise HTTPException(503,'Invalid token expiry configuration')
                if expires<=datetime.now(timezone.utc):raise HTTPException(401,'Access token expired')
            if not isinstance(identity.get('name','configured-user'),str):raise HTTPException(503,'Invalid user configuration')
            for field in ['user_id','employee_id']:
                if field in identity and not isinstance(identity[field],str):raise HTTPException(503,'Invalid user identity configuration')
            branches=identity.get('branches',[])
            if not isinstance(branches,list) or any(not isinstance(v,str) for v in branches):
                raise HTTPException(503,'Invalid branch permission configuration')
            return {**identity,'user_id':identity.get('user_id') or identity.get('name','configured-user'),'branches':list(set(branches))}
    raise HTTPException(401,'Access token required')

def authorize_branch(identity,branch):
    if branch not in identity['branches']:raise HTTPException(403,'No permission for this branch')

def financial_user(identity):
    if identity['role'] not in ('owner','manager','accountant'):raise HTTPException(403,'Financial access requires owner/accountant role')
