from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.interactive_portfolio import RebalanceConstraint, ScenarioRequest
from trading_ai.ui.services.interactive_portfolio_service import InteractivePortfolioService

router = APIRouter(prefix="/api/v1/interactive-portfolio", tags=["interactive-portfolio"])

def service():
    return InteractivePortfolioService()

@router.get("/summary")
def summary(account_id: str = "paper-account", svc=Depends(service)):
    return svc.summary(account_id)

@router.get("/positions")
def positions(account_id: str = "paper-account", svc=Depends(service)):
    return svc.positions(account_id)

@router.get("/exposure-matrix")
def exposure_matrix(account_id: str = "paper-account", svc=Depends(service)):
    return svc.exposure_matrix(account_id)

@router.post("/scenarios")
def scenarios(request: ScenarioRequest, svc=Depends(service)):
    return svc.scenarios(request)

@router.post("/rebalance-proposal")
def rebalance(account_id: str, constraints: RebalanceConstraint, svc=Depends(service)):
    return svc.rebalance(account_id, constraints)
