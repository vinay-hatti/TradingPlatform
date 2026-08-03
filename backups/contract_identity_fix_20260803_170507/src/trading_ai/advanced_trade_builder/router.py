from fastapi import APIRouter,Depends,HTTPException,Request,Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .contracts import BuildTradePlanRequest,TradeLeg,LegSide,OptionRight
from .repository import TradePlanRepository
from .service import AdvancedTradeBuilderService
router=APIRouter(prefix='/api/v1/trade-builder',tags=['trade-builder'])
def env(req,data,**meta):return ApiEnvelope(request_id=req.state.request_id,data=data,metadata=meta)
def dto(m):return AdvancedTradeBuilderService._dto(m).to_dict()
@router.get('/plans',response_model=ApiEnvelope)
def plans(request:Request,opportunity_id:str|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  items=TradePlanRepository(s).list(opportunity_id);return env(request,[dto(x) for x in items],count=len(items))
@router.post('/plans',response_model=ApiEnvelope)
def build(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  legs=tuple(TradeLeg(side=LegSide(x['side']),quantity=int(x['quantity']),option_right=OptionRight(x['option_right']),strike=float(x['strike']),expiry=x['expiry'],limit_price=float(x['limit_price']),delta=x.get('delta'),gamma=x.get('gamma'),theta=x.get('theta'),vega=x.get('vega'),option_symbol=x.get('option_symbol')) for x in payload['legs'])
  r=BuildTradePlanRequest(opportunity_id=payload['opportunity_id'],expected_opportunity_version=int(payload['expected_opportunity_version']),account_id=payload['account_id'],strategy=payload['strategy'],capital=float(payload['capital']),risk_budget_pct=float(payload['risk_budget_pct']),legs=legs,actor=actor,notes=payload.get('notes',''))
  with SessionLocal() as s:return env(request,AdvancedTradeBuilderService(s).build(r).to_dict())
 except KeyError as e:raise HTTPException(404,str(e))
 except (ValueError,RuntimeError) as e:raise HTTPException(409,str(e))
@router.post('/plans/{plan_id}/transitions',response_model=ApiEnvelope)
def transition(plan_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,AdvancedTradeBuilderService(s).transition(plan_id,int(payload['expected_version']),payload['new_state'],actor,payload['reason']).to_dict())
 except KeyError as e:raise HTTPException(404,str(e))
 except (ValueError,RuntimeError) as e:raise HTTPException(409,str(e))
@router.get('/plans/{plan_id}/audit',response_model=ApiEnvelope)
def audit(plan_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  items=TradePlanRepository(s).audit(plan_id);return env(request,[{'audit_id':x.audit_id,'trade_plan_version':x.trade_plan_version,'event_type':x.event_type,'actor':x.actor,'reason':x.reason,'event_timestamp':x.event_timestamp,'payload':x.payload_json} for x in items],count=len(items))
