from fastapi import APIRouter, Depends, HTTPException, Query, Request
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access
from .service import PortfolioRiskAllocationService
from .decision_intelligence import InstitutionalDecisionIntelligenceService
router=APIRouter(prefix='/api/v1/portfolio-risk-allocation',tags=['portfolio-risk-allocation'])
def env(request,data,**metadata): return ApiEnvelope(request_id=request.state.request_id,data=data,metadata=metadata)
@router.post('/build',response_model=ApiEnvelope)
def build(request:Request,payload:dict|None=None,actor:str=Depends(require_mutation_access)):
 try:return env(request,PortfolioRiskAllocationService(SessionLocal).build((payload or {}).get('portfolio_id','PAPER-PRIMARY'),actor))
 except Exception as exc: raise HTTPException(409,str(exc)) from exc
@router.get('/current',response_model=ApiEnvelope)
def current(request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),_:str=Depends(require_access)): return env(request,PortfolioRiskAllocationService(SessionLocal).current(portfolio_id))
@router.post('/fit',response_model=ApiEnvelope)
def fit(request:Request,payload:dict,actor:str=Depends(require_mutation_access)): return env(request,PortfolioRiskAllocationService(SessionLocal).assess(payload.get('candidate',payload),payload.get('portfolio_id','PAPER-PRIMARY')))
@router.post('/stress',response_model=ApiEnvelope)
def stress(request:Request,payload:dict|None=None,actor:str=Depends(require_mutation_access)): return env(request,PortfolioRiskAllocationService(SessionLocal).stress((payload or {}).get('portfolio_id','PAPER-PRIMARY')))

@router.post('/decision-intelligence/build',response_model=ApiEnvelope)
def build_decision_intelligence(request:Request,payload:dict|None=None,actor:str=Depends(require_mutation_access)):
 data=payload or {}; ids=data.get('opportunity_ids')
 return env(request,InstitutionalDecisionIntelligenceService(SessionLocal).build(data.get('portfolio_id','PAPER-PRIMARY'),ids,data.get('limit')))

@router.get('/decision-intelligence/rankings',response_model=ApiEnvelope)
def decision_rankings(request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),limit:int=Query(100,ge=1,le=1000),_:str=Depends(require_access)):
 data=InstitutionalDecisionIntelligenceService(SessionLocal).rankings(portfolio_id,limit)
 return env(request,data,count=len(data))

@router.get('/decision-intelligence/{opportunity_id}',response_model=ApiEnvelope)
def current_decision_intelligence(opportunity_id:str,request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),_:str=Depends(require_access)):
 data=InstitutionalDecisionIntelligenceService(SessionLocal).current(opportunity_id,portfolio_id)
 if data is None: raise HTTPException(404,'Portfolio-aware decision intelligence not found')
 return env(request,data)

from .optimizer import PortfolioOptimizationService
from .orchestration import Milestone64ContinuousPortfolioIntelligenceService

@router.post('/optimizer/build',response_model=ApiEnvelope)
def build_optimizer(request:Request,payload:dict|None=None,actor:str=Depends(require_mutation_access)):
 data=payload or {}
 return env(request,PortfolioOptimizationService(SessionLocal).build(
  data.get('portfolio_id','PAPER-PRIMARY'),
  rebuild_decisions=bool(data.get('rebuild_decisions',True)),
  actor=actor,
  policy=data.get('policy'),
 ))

@router.get('/optimizer/current',response_model=ApiEnvelope)
def current_optimizer(request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),_:str=Depends(require_access)):
 data=PortfolioOptimizationService(SessionLocal).current(portfolio_id)
 if data is None: raise HTTPException(404,'Portfolio optimization snapshot not found')
 return env(request,data)

@router.get('/optimizer/recommendations',response_model=ApiEnvelope)
def optimizer_recommendations(request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),status:str|None=Query(None),_:str=Depends(require_access)):
 data=PortfolioOptimizationService(SessionLocal).recommendations(portfolio_id,status)
 return env(request,data,count=len(data))

@router.get('/optimizer/publication',response_model=ApiEnvelope)
def optimizer_publication(request:Request,portfolio_id:str=Query('PAPER-PRIMARY'),_:str=Depends(require_access)):
 data=PortfolioOptimizationService(SessionLocal).publication(portfolio_id)
 if data is None: raise HTTPException(404,'Portfolio allocation publication not found')
 return env(request,data)

@router.post('/continuous-intelligence/run',response_model=ApiEnvelope)
def run_continuous_intelligence(request:Request,payload:dict|None=None,actor:str=Depends(require_mutation_access)):
 data=payload or {}
 return env(request,Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(data.get('portfolio_id','PAPER-PRIMARY'),actor))
