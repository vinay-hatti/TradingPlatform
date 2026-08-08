from fastapi import APIRouter,Depends,HTTPException,Request
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .service import ExecutionIntelligenceService
from .policy import load_execution_intelligence_policy
router=APIRouter(prefix='/api/v1/execution-intelligence',tags=['execution-intelligence'])
def env(req,data,**meta):return ApiEnvelope(request_id=req.state.request_id,data=data,metadata=meta)
def fail(e):return HTTPException(404 if isinstance(e,KeyError) else 409,str(e))
@router.get('/policy',response_model=ApiEnvelope)
def policy(request:Request,_:str=Depends(require_access)):return env(request,load_execution_intelligence_policy().as_dict())
@router.post('/intents/{intent_id}/preflight',response_model=ApiEnvelope)
def preflight(intent_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionIntelligenceService(s).preflight(intent_id,actor,payload.get('reason') or 'Manual execution preflight'))
 except Exception as e:raise fail(e)
@router.post('/intents/{intent_id}/working-assessment',response_model=ApiEnvelope)
def working(intent_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,ExecutionIntelligenceService(s).assess_working(intent_id,actor,payload.get('reason') or 'Manual working-order assessment'))
 except Exception as e:raise fail(e)
@router.get('/intents/{intent_id}/latest',response_model=ApiEnvelope)
def latest(intent_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,ExecutionIntelligenceService(s).latest(intent_id))
@router.get('/dashboard',response_model=ApiEnvelope)
def dashboard(request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,ExecutionIntelligenceService(s).dashboard())
