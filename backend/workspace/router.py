from fastapi import APIRouter,Depends,Header,HTTPException,Query
from backend.security import user
from backend.erp.router import service
from backend.erp.service import ERPError
from backend.workspace.service import Workspace

router=APIRouter(prefix='/api/workspace',tags=['Employee / manager / owner'])

def execute(fn):
    try:return fn()
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except ERPError as exc:raise HTTPException(422,str(exc)) from exc

def body_fields(body,allowed,required):
    if set(body)-set(allowed) or set(required)-set(body):raise HTTPException(422,'Invalid request fields')

@router.post('/session/open')
async def open_session(body: dict,identity=Depends(user)):
    body_fields(body,['branch_id'],['branch_id'])
    return execute(lambda:Workspace(service()).session(identity,body['branch_id'],True))

@router.get('/session')
async def session(branch: str='q1',identity=Depends(user)):
    return execute(lambda:Workspace(service()).session(identity,branch,False))

@router.post('/actions')
async def action(body: dict,idempotency_key: str=Header(default=''),identity=Depends(user)):
    body_fields(body,['branch_id','kind','payload'],['branch_id','kind','payload'])
    return execute(lambda:Workspace(service()).action(identity,body['branch_id'],body['kind'],body['payload'],idempotency_key))

@router.get('/shifts')
async def shifts(branch: str='q1',identity=Depends(user)):
    return execute(lambda:Workspace(service()).shift_summary(identity,branch))

@router.post('/quote')
async def preview(body: dict,identity=Depends(user)):
    body_fields(body,['branch_id','items','activation_key'],['branch_id','items'])
    if body.get('activation_key') is not None and not isinstance(body['activation_key'],str):raise HTTPException(422,'Invalid key')
    return execute(lambda:Workspace(service()).quote_order(identity,body['branch_id'],body['items'],body.get('activation_key')))

@router.post('/checkout')
async def checkout(body: dict,idempotency_key: str=Header(default=''),identity=Depends(user)):
    body_fields(body,['document','activation_key','order_id','order_revision','expected_gross_minor'],['document'])
    if not isinstance(body['document'],dict) or (body.get('activation_key') is not None and not isinstance(body['activation_key'],str)):raise HTTPException(422,'Invalid checkout payload')
    if body.get('order_id') is not None and not isinstance(body['order_id'],str):raise HTTPException(422,'Invalid order identifier')
    for field in ('order_revision','expected_gross_minor'):
        if body.get(field) is not None and (type(body[field]) is not int or body[field]<0):raise HTTPException(422,'Invalid checkout amount or revision')
    return execute(lambda:Workspace(service()).sale(identity,body['document'],idempotency_key,body.get('activation_key'),body.get('order_id'),body.get('order_revision'),body.get('expected_gross_minor')))

@router.get('/receipt/{document_id}')
async def receipt(document_id: str,identity=Depends(user)):
    return execute(lambda:Workspace(service()).receipt(identity,document_id))

@router.get('/management')
async def management(branch: str='q1',month: str=Query(...),day: str | None=None,identity=Depends(user)):
    return execute(lambda:Workspace(service()).management(identity,branch,month,day))

@router.get('/owner')
async def owner(month: str=Query(...),identity=Depends(user)):
    return execute(lambda:Workspace(service()).owner_summary(identity,month))

@router.post('/payroll/accrue')
async def payroll(body: dict,idempotency_key: str=Header(default=''),identity=Depends(user)):
    body_fields(body,['branch_id','month','date'],['branch_id','month','date'])
    return execute(lambda:Workspace(service()).accrue_payroll(identity,body['branch_id'],body['month'],body['date'],idempotency_key))
