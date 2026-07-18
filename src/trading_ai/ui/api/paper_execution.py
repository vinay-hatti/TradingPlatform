from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from trading_ai.ui.models.paper_execution import PaperExecutionState
from trading_ai.ui.services.paper_execution_service import PaperExecutionService


router = APIRouter(
    prefix="/api/v1/paper-execution",
    tags=["paper-execution"],
)


class SynchronizeRequest(BaseModel):
    market_prices: dict[str, float] = Field(default_factory=dict)


class SimulateFillRequest(BaseModel):
    market_prices: dict[str, float]
    max_fill_quantity: int | None = Field(default=None, gt=0)


def service() -> PaperExecutionService:
    return PaperExecutionService()


@router.get("", response_model=PaperExecutionState)
def state(execution_service: PaperExecutionService = Depends(service)):
    return execution_service.state()


@router.post("/synchronize")
def synchronize(
    request: SynchronizeRequest,
    execution_service: PaperExecutionService = Depends(service),
):
    submitted = execution_service.synchronize_orders(request.market_prices)
    return {
        "status": "COMPLETE",
        "submitted_orders": submitted,
        "state": execution_service.state(),
    }


@router.post("/simulate-fills")
def simulate_fills(
    request: SimulateFillRequest,
    execution_service: PaperExecutionService = Depends(service),
):
    fill_quantity = execution_service.simulate_open_order_fills(
        request.market_prices,
        max_fill_quantity=request.max_fill_quantity,
    )
    return {
        "status": "COMPLETE",
        "filled_quantity": fill_quantity,
        "state": execution_service.state(),
    }


@router.get("/reconciliation")
def reconciliation(
    execution_service: PaperExecutionService = Depends(service),
):
    return execution_service.reconciliation()
