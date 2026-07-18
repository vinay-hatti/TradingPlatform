from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ExecutionOrder(BaseModel):
    order_id: str
    client_order_id: str | None = None
    symbol: str
    contract: str | None = None
    strategy: str = "Unknown"
    side: str = "UNKNOWN"
    order_type: str = "UNKNOWN"
    time_in_force: str | None = None
    quantity: float = 0.0
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    limit_price: float | None = None
    stop_price: float | None = None
    average_fill_price: float | None = None
    status: str = "UNKNOWN"
    broker_status: str | None = None
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    source: str
    can_cancel: bool = False
    can_replace: bool = False


class ExecutionFill(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    quantity: float
    price: float
    commission: float = 0.0
    liquidity: str | None = None
    venue: str | None = None
    filled_at: datetime | None = None
    source: str


class ExecutionQuality(BaseModel):
    submitted_orders: int = 0
    open_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    fill_rate_pct: float | None = None
    average_fill_latency_ms: float | None = None
    average_slippage_bps: float | None = None
    total_slippage: float | None = None
    total_commission: float = 0.0
    reconciliation_breaks: int = 0
    stale_orders: int = 0


class ExecutionAlert(BaseModel):
    severity: str
    code: str
    message: str
    order_id: str | None = None
    detected_at: datetime


class ExecutionConsoleResponse(BaseModel):
    generated_at: datetime
    available: bool
    stale: bool
    age_seconds: float | None = None
    command_mode: str
    source_detail: str
    quality: ExecutionQuality
    orders: list[ExecutionOrder] = Field(default_factory=list)
    fills: list[ExecutionFill] = Field(default_factory=list)
    alerts: list[ExecutionAlert] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class CancelOrderRequest(BaseModel):
    reason: str = "Cancelled from institutional workstation"


class ReplaceOrderRequest(BaseModel):
    quantity: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    reason: str = "Replaced from institutional workstation"


class OrderCommandResult(BaseModel):
    accepted: bool
    order_id: str
    action: str
    message: str
    requested_at: datetime
