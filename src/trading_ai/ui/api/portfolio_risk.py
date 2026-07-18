from fastapi import APIRouter, Depends

from trading_ai.ui.models.portfolio_risk import PortfolioRiskResponse
from trading_ai.ui.services.portfolio_risk_service import PortfolioRiskService

router = APIRouter(prefix="/api/v1", tags=["portfolio-risk"])


def service() -> PortfolioRiskService:
    return PortfolioRiskService()


@router.get("/portfolio-risk", response_model=PortfolioRiskResponse)
def portfolio_risk(
    cockpit: PortfolioRiskService = Depends(service),
):
    return cockpit.get()
