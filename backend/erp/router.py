"""Private local ERP API. Configure tokens in environment; no hardcoded credentials."""
import os
from pathlib import Path
from fastapi import APIRouter,Depends,Header,HTTPException,Query
from backend.erp.service import ERP,ERPError
from backend.security import user,authorize_branch,financial_user
router=APIRouter(prefix='/api/erp',tags=['Restaurant operations MVP'])

def service():
    return ERP(Path(os.environ.get('BEP_ERP_DATABASE','backend/data/erp.sqlite3')),
        os.environ.get('BEP_ERP_CURRENCY','GBP'),os.environ.get('BEP_ERP_JURISDICTION','GB'))

@router.get('/status')
async def backend_status():
    return {'engine':'bep-python-sql','credentials_configured':bool(os.environ.get('BEP_ERP_USERS'))}

@router.get('/report')
async def report(branch: str='q1',start: str='0001-01-01',end: str='9999-12-31',identity=Depends(user)):
    financial_user(identity)
    authorize_branch(identity,branch)
    try:return service().report(branch,start,end)
    except ERPError as exc:raise HTTPException(422,str(exc)) from exc

@router.post('/documents')
async def create_document(payload: dict,idempotency_key: str=Header(default=''),identity=Depends(user)):
    authorize_branch(identity,payload.get('branch_id'))
    if identity['role'] in ('cashier','manager') and payload.get('kind') in ('sale','collect'):
        from backend.workspace.service import Workspace
        try:return Workspace(service()).sale(identity,payload,idempotency_key)
        except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
        except ERPError as exc:raise HTTPException(422,str(exc)) from exc
    try:return service().post(payload,idempotency_key,identity.get('name','configured-user'),identity['role'])
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except ERPError as exc:raise HTTPException(422,str(exc)) from exc

@router.get('/forecast')
async def forecast_report(branch: str='q1',horizon: int=Query(3,ge=1,le=6),as_of: str | None=None,identity=Depends(user)):
    from backend.erp.forecast import forecast_ledger
    from backend.integrity import IntegrityError
    financial_user(identity);authorize_branch(identity,branch)
    try:return forecast_ledger(service(),branch,horizon,as_of)
    except ValueError as exc:
        if isinstance(exc,IntegrityError):raise
        raise HTTPException(422,str(exc)) from exc
