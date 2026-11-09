"""Authenticated local API. Financial data requires explicit branch grants."""
import os
from contextlib import closing
from pathlib import Path
from fastapi import Depends,FastAPI,HTTPException,Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.analytics import connect,monthly_report,forecast
from backend.data_quality import verified_periods
from backend.erp.router import router as erp_router
from backend.workspace.router import router as workspace_router
from backend.accounts.router import router as accounts_router
from backend.security import user,authorize_branch,financial_user
from backend.integrity import IntegrityError
from backend.http_security import SecurityGuard

app=FastAPI(title='Bếp Finance Analytics',version='0.2.0')
app.add_middleware(SecurityGuard)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.environ.get('BEP_ALLOWED_HOSTS','localhost,127.0.0.1,[::1],test').split(','))
DB=Path(os.environ.get('BEP_DATABASE','backend/data/finance.sqlite3'))

@app.exception_handler(IntegrityError)
async def integrity_error(request,error):
    return JSONResponse(status_code=409,content={'detail':'Data integrity verification failed. Stop processing and investigate.'})

def database():
    if not DB.is_file():raise HTTPException(503,'Initialize and import the database first')
    return connect(DB)

@app.get('/api/reports/monthly')
async def reports(branch: str | None=None,start: str | None=None,end: str | None=None,identity=Depends(user)):
    financial_user(identity)
    if branch is not None:authorize_branch(identity,branch)
    try:
        with closing(database()) as conn:
            conn.execute('BEGIN')
            rows=monthly_report(conn,branch,start,end,identity['branches'])
            for selected in {row['branch_id'] for row in rows}:
                verified_periods(conn,selected,[row['month'] for row in rows if row['branch_id']==selected])
            return {'currency':'VND','basis':'recognized_net_entries','quality':'review_signatures_verified',
                'filters':{'branch':branch,'start':start,'end':end},'rows':rows}
    except ValueError as exc:
        if isinstance(exc,IntegrityError):raise
        raise HTTPException(422,str(exc)) from exc

@app.get('/api/forecast')
async def forecast_report(branch: str,horizon: int=Query(3,ge=1,le=6),as_of: str | None=None,identity=Depends(user)):
    financial_user(identity);authorize_branch(identity,branch)
    try:
        with closing(database()) as conn:
            conn.execute('BEGIN')
            return forecast(conn,branch,horizon,as_of)
    except ValueError as exc:
        if isinstance(exc,IntegrityError):raise
        raise HTTPException(422,str(exc)) from exc

app.include_router(accounts_router)
app.include_router(erp_router)
app.include_router(workspace_router)
app.mount('/',StaticFiles(directory=Path(__file__).parent.parent/'dist',html=True),name='demo')
