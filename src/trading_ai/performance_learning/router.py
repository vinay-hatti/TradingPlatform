from fastapi import APIRouter,Depends,HTTPException,Request,Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access,require_mutation_access
from .repository import PerformanceLearningRepository
from .service import PerformanceLearningService
router=APIRouter(prefix='/api/v1/performance-learning',tags=['performance-learning'])
def env(r,d,**m):return ApiEnvelope(request_id=r.state.request_id,data=d,metadata=m)
def fail(e):return HTTPException(404 if isinstance(e,KeyError) else 409,str(e))
@router.post('/positions/{position_id}/observations',response_model=ApiEnvelope)
def capture(position_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PerformanceLearningService(s).capture_position(position_id,actor))
 except Exception as e:raise fail(e)
@router.post('/portfolios/{portfolio_id}/reports',response_model=ApiEnvelope)
def generate(portfolio_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 from .outcome_engine import Milestone65LearningService
 with SessionLocal() as s:
  result=Milestone65LearningService(s).build_command_center(portfolio_id,actor)
  report=PerformanceLearningRepository(s).latest_report(portfolio_id)
  return env(request,report.payload_json if report else result)
@router.get('/portfolios/{portfolio_id}/report',response_model=ApiEnvelope)
def latest(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  x=PerformanceLearningRepository(s).latest_report(portfolio_id);return env(request,x.payload_json if x else None)
@router.get('/portfolios/{portfolio_id}/reports',response_model=ApiEnvelope)
def history(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 with SessionLocal() as s:
  xs=PerformanceLearningRepository(s).reports(portfolio_id);return env(request,[x.payload_json for x in xs],count=len(xs))
@router.get('/policies',response_model=ApiEnvelope)
def policies(request:Request,name:str|None=Query(None),_:str=Depends(require_access)):
 with SessionLocal() as s:
  svc=PerformanceLearningService(s);xs=svc.repo.policies(name);return env(request,[svc.dto_policy(x) for x in xs],count=len(xs))
@router.post('/policies',response_model=ApiEnvelope)
def propose(payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PerformanceLearningService(s).propose_policy(payload['policy_name'],payload['parameters'],payload.get('evidence',{}),actor,payload['reason']))
 except Exception as e:raise fail(e)
@router.post('/policies/{policy_id}/transitions',response_model=ApiEnvelope)
def transition(policy_id:str,payload:dict,request:Request,actor:str=Depends(require_mutation_access)):
 try:
  with SessionLocal() as s:return env(request,PerformanceLearningService(s).transition_policy(policy_id,payload['target_state'],actor,payload['reason']))
 except Exception as e:raise fail(e)

@router.post('/portfolios/{portfolio_id}/command-center/build',response_model=ApiEnvelope)
def build_command_center(portfolio_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 from .outcome_engine import Milestone65LearningService
 with SessionLocal() as s:return env(request,Milestone65LearningService(s).build_command_center(portfolio_id,actor))

@router.get('/portfolios/{portfolio_id}/publication',response_model=ApiEnvelope)
def current_learning_publication(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 from .outcome_engine import Milestone65LearningService
 with SessionLocal() as s:return env(request,Milestone65LearningService(s).current_publication(portfolio_id))

@router.post('/portfolios/{portfolio_id}/outcomes/reconstruct',response_model=ApiEnvelope)
def reconstruct_outcomes(portfolio_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 from .outcome_engine import Milestone65LearningService
 with SessionLocal() as s:return env(request,Milestone65LearningService(s).reconstruct_outcomes(portfolio_id))

@router.post('/portfolios/{portfolio_id}/counterfactuals/evaluate',response_model=ApiEnvelope)
def evaluate_counterfactuals(portfolio_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 from .outcome_engine import Milestone65LearningService
 with SessionLocal() as s:return env(request,Milestone65LearningService(s).evaluate_counterfactuals(portfolio_id))

@router.post('/portfolios/{portfolio_id}/learning-cycle',response_model=ApiEnvelope)
def run_learning_cycle(portfolio_id:str,request:Request,actor:str=Depends(require_mutation_access)):
 from .continuous_learning import ContinuousLearningService
 with SessionLocal() as s:return env(request,ContinuousLearningService(s).run_cycle(portfolio_id))

@router.get('/portfolios/{portfolio_id}/learning-dashboard',response_model=ApiEnvelope)
def learning_dashboard(portfolio_id:str,request:Request,_:str=Depends(require_access)):
 from .continuous_learning import ContinuousLearningService
 with SessionLocal() as s:return env(request,ContinuousLearningService(s).dashboard(portfolio_id))
