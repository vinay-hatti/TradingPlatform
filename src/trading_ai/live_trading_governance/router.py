from fastapi import APIRouter,Depends,HTTPException,Request
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .service import LiveTradingGovernanceService
router=APIRouter(prefix='/api/v1/live-trading-governance',tags=['live-trading-governance'])
def env(r,d): return ApiEnvelope(request_id=r.state.request_id,data=d,metadata={})
@router.get('/status/{portfolio_id}',response_model=ApiEnvelope)
def status(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).status(portfolio_id))
@router.post('/policies/{portfolio_id}',response_model=ApiEnvelope)
def policy(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).create_policy(portfolio_id,actor,payload))
@router.post('/approvals/{portfolio_id}/request',response_model=ApiEnvelope)
def request_approval(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).request_approval(portfolio_id,actor,payload.get('reason','')))
@router.post('/approvals/{approval_id}/approve',response_model=ApiEnvelope)
def approve(approval_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:
  try:return env(request,LiveTradingGovernanceService(s).approve(approval_id,actor,payload.get('reason','')))
  except KeyError:raise HTTPException(404,'Approval not found')
@router.post('/certifications/{portfolio_id}',response_model=ApiEnvelope)
def certify(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).certify(portfolio_id,actor,payload.get('evidence',{})))
@router.post('/activate/{portfolio_id}',response_model=ApiEnvelope)
def activate(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).activate(portfolio_id,actor,payload.get('confirmation','')))
@router.post('/halt/{portfolio_id}',response_model=ApiEnvelope)
def halt(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).halt(portfolio_id,actor,payload.get('reason','Operator halt'),payload.get('scope','ACCOUNT'),payload.get('scope_value','*'),payload.get('action','BLOCK_NEW_ORDERS')))
@router.post('/kill-switches/{switch_id}/clear',response_model=ApiEnvelope)
def clear(switch_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:
  try:return env(request,LiveTradingGovernanceService(s).clear_halt(switch_id,actor,payload.get('reason','')))
  except KeyError:raise HTTPException(404,'Kill switch not found')
@router.post('/evaluate/{portfolio_id}',response_model=ApiEnvelope)
def evaluate(portfolio_id:str,payload:dict,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,LiveTradingGovernanceService(s).evaluate_order(portfolio_id,payload.get('order',{}),payload.get('readiness',{})))
