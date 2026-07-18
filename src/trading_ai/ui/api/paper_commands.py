from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.paper_commands import (
    CommandDecision,
    PaperOrderCancelRequest,
    PaperOrderReplaceRequest,
    PaperOrderSubmitRequest,
    PaperTradingState,
)
from trading_ai.ui.services.paper_command_service import PaperCommandService


router = APIRouter(
    prefix="/api/v1/paper-commands",
    tags=["paper-commands"],
)


def service() -> PaperCommandService:
    return PaperCommandService()


@router.get("", response_model=PaperTradingState)
def paper_trading_state(
    command_service: PaperCommandService = Depends(service),
):
    return command_service.state()


@router.post("/orders", response_model=CommandDecision)
def submit_paper_order(
    request: PaperOrderSubmitRequest,
    command_service: PaperCommandService = Depends(service),
):
    decision = command_service.submit(request)
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail=decision.model_dump(mode="json"),
        )
    return decision


@router.post(
    "/orders/{order_id}/cancel",
    response_model=CommandDecision,
)
def cancel_paper_order(
    order_id: str,
    request: PaperOrderCancelRequest,
    command_service: PaperCommandService = Depends(service),
):
    decision = command_service.cancel(order_id, request)
    if decision.status == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=decision.model_dump(mode="json"))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.model_dump(mode="json"))
    return decision


@router.post(
    "/orders/{order_id}/replace",
    response_model=CommandDecision,
)
def replace_paper_order(
    order_id: str,
    request: PaperOrderReplaceRequest,
    command_service: PaperCommandService = Depends(service),
):
    decision = command_service.replace(order_id, request)
    if decision.status == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=decision.model_dump(mode="json"))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.model_dump(mode="json"))
    return decision
