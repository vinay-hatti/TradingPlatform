from fastapi import APIRouter,Depends,HTTPException,Request,Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .repository import PortfolioRepository
from .service import PortfolioIntelligenceService
router=APIRouter(prefix='/api/v1/portfolio-intelligence',tags=['portfolio-intelligence'])
def env(r,d,**m):return ApiEnvelope(request_id=r.state.request_id,data=d,metadata=m)
def fail(e):
 if isinstance(e,KeyError):return HTTPException(404,str(e))
 return HTTPException(409,str(e))
@router.get('/positions',response_model=ApiEnvelope)
def positions(request:Request,portfolio_id:str|None=Query(None),state:str|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  x=PortfolioRepository(s).list(portfolio_id,state);return env(request,[PortfolioIntelligenceService.dto(i) for i in x],count=len(x))
@router.post('/positions/from-trade-plan',response_model=ApiEnvelope)
def create(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PortfolioIntelligenceService(s).open_from_trade_plan(payload['trade_plan_id'],payload.get('portfolio_id','PAPER-PRIMARY'),payload['mark'],actor,payload.get('execution_id')))
 except Exception as e:raise fail(e)
@router.post('/positions/{id}/marks',response_model=ApiEnvelope)
def mark(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PortfolioIntelligenceService(s).update_mark(id,int(payload['expected_version']),payload['mark'],actor,payload.get('reason','Position mark updated')))
 except Exception as e:raise fail(e)
@router.post('/positions/{id}/actions',response_model=ApiEnvelope)
def action(id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PortfolioIntelligenceService(s).action(id,int(payload['expected_version']),payload['action'],actor,payload['reason'],float(payload.get('realized_pnl',0))))
 except Exception as e:raise fail(e)
@router.get('/positions/{id}/events',response_model=ApiEnvelope)
def events(id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  x=PortfolioRepository(s).events(id);return env(request,[{'event_id':i.event_id,'position_version':i.position_version,'event_type':i.event_type,'actor':i.actor,'reason':i.reason,'event_timestamp':i.event_timestamp,'payload':i.payload_json} for i in x],count=len(x))
@router.get('/positions/{id}/health',response_model=ApiEnvelope)
def health(id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  x=PortfolioRepository(s).health(id);return env(request,[{'health_snapshot_id':i.health_snapshot_id,'position_version':i.position_version,'snapshot_timestamp':i.snapshot_timestamp,'health_score':i.health_score,'direction':i.direction,'confidence':i.confidence,'payload':i.payload_json} for i in x],count=len(x))
@router.post('/positions/{id}/attribution',response_model=ApiEnvelope)
def attribution(id:str,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PortfolioIntelligenceService(s).attribution(id,actor))
 except Exception as e:raise fail(e)
@router.post('/portfolios/{portfolio_id}/snapshots',response_model=ApiEnvelope)
def snapshot(portfolio_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 with SessionLocal() as s:return env(request,PortfolioIntelligenceService(s).snapshot(portfolio_id,actor,float(payload.get('cash',0)),float(payload.get('buying_power',0))))
@router.get('/portfolios/{portfolio_id}/snapshot',response_model=ApiEnvelope)
def latest(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  x=PortfolioRepository(s).latest_snapshot(portfolio_id);return env(request,({'snapshot_id':x.snapshot_id,**x.payload_json} if x else None))
