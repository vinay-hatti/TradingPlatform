from fastapi import APIRouter,Depends,HTTPException,Request,Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .repository import ExecutionIntentRepository
from .service import ExecutionWorkspaceService
router=APIRouter(prefix='/api/v1/execution-workspace',tags=['execution-workspace'])
def env(req,data,**meta):return ApiEnvelope(request_id=req.state.request_id,data=data,metadata=meta)
def fail(e):return HTTPException(404 if isinstance(e,KeyError) else 409,str(e))
@router.get('/intents',response_model=ApiEnvelope)
def intents(request:Request,state:str|None=Query(None),portfolio_id:str|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  items=ExecutionIntentRepository(s).list(state,portfolio_id);return env(request,[ExecutionWorkspaceService.dto(x) for x in items],count=len(items))
@router.post('/intents/from-trade-plan/{trade_plan_id}',response_model=ApiEnvelope)
def create(trade_plan_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).create_from_trade_plan(trade_plan_id,actor,payload.get('portfolio_id')))
 except Exception as e:raise fail(e)
@router.post('/intents/{id}/transitions',response_model=ApiEnvelope)
def transition(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).transition(id,int(payload['expected_version']),payload['new_state'],actor,payload['reason']))
 except Exception as e:raise fail(e)
@router.post('/intents/{id}/submit',response_model=ApiEnvelope)
def submit(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).submit(id,int(payload['expected_version']),actor,payload['reason'],payload['confirmation']))
 except Exception as e:raise fail(e)
@router.post('/intents/{id}/synchronize',response_model=ApiEnvelope)
def sync(id:str,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).synchronize(id,actor))
 except Exception as e:raise fail(e)
@router.post('/intents/{id}/reprice',response_model=ApiEnvelope)
def reprice(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).reprice_working(id,int(payload['expected_version']),actor,payload['reason'],payload['confirmation']))
 except Exception as e:raise fail(e)
@router.post('/intents/{id}/cancel',response_model=ApiEnvelope)
def cancel(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).cancel(id,int(payload['expected_version']),actor,payload['reason']))
 except Exception as e:raise fail(e)

@router.post('/intents/{id}/retry',response_model=ApiEnvelope)
def retry(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionWorkspaceService(s).retry_terminal(id,int(payload['expected_version']),actor,payload['reason']))
 except Exception as e:raise fail(e)
@router.get('/trade-plans/{trade_plan_id}/attempts',response_model=ApiEnvelope)
def attempts(trade_plan_id:str,request:Request,trade_plan_version:int|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  if trade_plan_version is None:
   from trading_ai.advanced_trade_builder.models import TradePlanModel
   tp=s.get(TradePlanModel,trade_plan_id)
   if not tp:raise fail(KeyError('Trade plan not found'))
   trade_plan_version=int(tp.version)
  rows=ExecutionIntentRepository(s).attempts(trade_plan_id,int(trade_plan_version));return env(request,[ExecutionWorkspaceService.dto(x) for x in rows],count=len(rows))
@router.get('/intents/{id}/audit',response_model=ApiEnvelope)
def audit(id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  items=ExecutionIntentRepository(s).audit(id);return env(request,[{'event_id':x.event_id,'execution_intent_version':x.execution_intent_version,'event_type':x.event_type,'previous_state':x.previous_state,'new_state':x.new_state,'actor':x.actor,'reason':x.reason,'event_timestamp':x.event_timestamp,'payload':x.payload_json} for x in items],count=len(items))
@router.get('/routing-status/{portfolio_id}',response_model=ApiEnvelope)
def status(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 try:
  from trading_ai.broker.ibkr.order_service import IbkrPaperOrderGovernanceService
  return env(request,IbkrPaperOrderGovernanceService(SessionLocal).status(portfolio_id))
 except Exception as e:raise fail(e)
