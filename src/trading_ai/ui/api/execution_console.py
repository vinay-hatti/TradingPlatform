from fastapi import APIRouter, Depends

from trading_ai.ui.models.execution_console import (
    CancelOrderRequest,
    ExecutionConsoleResponse,
    OrderCommandResult,
    ReplaceOrderRequest,
)
from trading_ai.ui.services.execution_console_service import ExecutionConsoleService

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


def service():
    return ExecutionConsoleService()


@router.get("", response_model=ExecutionConsoleResponse)
def execution_console(console: ExecutionConsoleService = Depends(service)):
    return console.get()


@router.post("/orders/{order_id}/cancel", response_model=OrderCommandResult)
def cancel_order(
    order_id: str,
    request: CancelOrderRequest,
    console: ExecutionConsoleService = Depends(service),
):
    return console.cancel(order_id, request)


@router.post("/orders/{order_id}/replace", response_model=OrderCommandResult)
def replace_order(
    order_id: str,
    request: ReplaceOrderRequest,
    console: ExecutionConsoleService = Depends(service),
):
    return console.replace(order_id, request)
