from fastapi import APIRouter,Depends,HTTPException,Request
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .service import ProductionOperationsService
router=APIRouter(prefix='/api/v1/production-operations',tags=['production-operations'])
def env(r,d,**m):return ApiEnvelope(request_id=r.state.request_id,data=d,metadata=m)
@router.get('/dashboard',response_model=ApiEnvelope)
def dashboard(request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,ProductionOperationsService(s).dashboard())
@router.get('/readiness',response_model=ApiEnvelope)
def readiness(request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:return env(request,ProductionOperationsService(s).readiness())
@router.post('/workflows/daily-cycle',response_model=ApiEnvelope)
def run_cycle(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,ProductionOperationsService(s).run_workflow(payload.get('mode','SIMULATION'),actor,bool(payload.get('continue_on_error'))))
@router.post('/alerts/{alert_id}/acknowledge',response_model=ApiEnvelope)
def ack(alert_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:
  try:return env(request,ProductionOperationsService(s).acknowledge(alert_id,actor))
  except KeyError:raise HTTPException(404,'Alert not found')
@router.post('/recoveries',response_model=ApiEnvelope)
def recover(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,ProductionOperationsService(s).recover(payload['action_type'],payload.get('target_type','PLATFORM'),payload.get('target_id','PLATFORM'),actor,payload.get('reason','Operator recovery')))
