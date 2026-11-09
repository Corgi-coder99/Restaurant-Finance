import os
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from backend.accounts.service import Accounts,AuthError
from backend.security import user
router=APIRouter(prefix='/api/auth',tags=['Password accounts'])
def run(fn):
 try:return fn()
 except PermissionError as e:raise HTTPException(403,str(e)) from e
 except AuthError as e:raise HTTPException(422,str(e)) from e

def fields(body,keys):
 if set(body)!=set(keys):raise HTTPException(422,'Invalid authentication fields')

@router.get('/status')
async def status():return {'password_accounts':len(os.environ.get('BEP_AUDIT_KEY',''))>=32,'email_recovery':all(os.environ.get(k) for k in ('BEP_SMTP_HOST','BEP_SMTP_USER','BEP_SMTP_PASSWORD','BEP_PUBLIC_URL'))}
@router.post('/accounts')
async def create(body:dict,identity=Depends(user)):return run(lambda:Accounts().create(identity,body))
@router.post('/login')
async def login(body:dict,response:Response):
 fields(body,['email','password','role']);token,identity=run(lambda:Accounts().login(body['email'],body['password'],body['role']))
 response.set_cookie('bep_session',token,max_age=8*3600,httponly=True,secure=os.environ.get('BEP_COOKIE_SECURE','true')!='false',samesite='strict',path='/')
 return {'identity':identity}
@router.get('/me')
async def me(identity=Depends(user)):return {'identity':identity}
@router.post('/logout')
async def logout(request:Request,response:Response):
 run(lambda:Accounts().logout(request.cookies.get('bep_session','')));response.delete_cookie('bep_session',path='/');return {'status':'ok'}
@router.post('/password')
async def change(body:dict,response:Response,identity=Depends(user)):
 fields(body,['current_password','new_password']);run(lambda:Accounts().change(identity,body['current_password'],body['new_password']));response.delete_cookie('bep_session',path='/');return {'status':'ok'}
@router.post('/forgot')
async def forgot(body:dict):
 fields(body,['email']);run(lambda:Accounts().recovery(body['email']));return {'status':'If this account exists, a recovery link has been sent'}
@router.post('/reset')
async def reset(body:dict):
 fields(body,['token','password']);run(lambda:Accounts().reset(body['token'],body['password']));return {'status':'ok'}
