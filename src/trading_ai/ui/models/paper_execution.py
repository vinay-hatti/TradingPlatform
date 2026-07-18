from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FillStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PaperFill(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    quantity: int
    price: float
    fees: float = 0.0
    occurred_at: datetime


class PaperPosition(BaseModel):
    symbol: str
    quantity: int
    average_price: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    updated_at: datetime


class BrokerPaperOrder(BaseModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: int
    filled_quantity: int = 0
    remaining_quantity: int
    limit_price: float | None = None
    status: FillStatus
    submitted_at: datetime
    updated_at: datetime
    fills: list[PaperFill] = Field(default_factory=list)


class ReconciliationIssue(BaseModel):
    issue_type: str
    severity: str
    resource_id: str
    detail: str


class ReconciliationReport(BaseModel):
    generated_at: datetime
    local_order_count: int
    broker_order_count: int
    local_position_count: int
    broker_position_count: int
    matched_orders: int
    matched_positions: int
    issue_count: int
    issues: list[ReconciliationIssue] = Field(default_factory=list)


class PaperExecutionSummary(BaseModel):
    environment: str = "PAPER"
    broker_adapter: str = "LOCAL_PAPER_BROKER"
    live_trading_enabled: bool = False
    total_orders: int = 0
    open_orders: int = 0
    total_fills: int = 0
    total_positions: int = 0
    gross_market_value: float = 0.0
    total_unrealized_pnl: float = 0.0
    reconciliation_status: str = "UNKNOWN"


class PaperExecutionState(BaseModel):
    generated_at: datetime
    summary: PaperExecutionSummary
    orders: list[BrokerPaperOrder] = Field(default_factory=list)
    fills: list[PaperFill] = Field(default_factory=list)
    positions: list[PaperPosition] = Field(default_factory=list)
    reconciliation: ReconciliationReport
    notices: list[str] = Field(default_factory=list)
