from fastapi import APIRouter, Depends
from trading_ai.ui.models.research_workbench import ReplayRequest, ScannerQuery
from trading_ai.ui.services.research_workbench_service import ResearchWorkbenchService

router=APIRouter(prefix="/api/v1/research-workbench",tags=["research-workbench"])
def service(): return ResearchWorkbenchService()

@router.get("/snapshot")
def snapshot(svc=Depends(service)): return svc.snapshot()

@router.post("/scanner")
def scanner(request: ScannerQuery,svc=Depends(service)): return svc.scanner(request)

@router.get("/feature-importance")
def feature_importance(svc=Depends(service)): return svc.feature_importance()

@router.get("/walk-forward")
def walk_forward(svc=Depends(service)): return svc.walk_forward_runs()

@router.post("/replay")
def replay(request: ReplayRequest,svc=Depends(service)): return svc.replay(request)
