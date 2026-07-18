from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PaperOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PaperOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PaperOrderStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    REJECTED = "REJECTED"


class GovernedActor(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class PaperOrderSubmitRequest(BaseModel):
    environment: Literal["PAPER", "SIMULATION"] = "PAPER"
    symbol: str = Field(min_length=1, max_length=20)
    instrument_type: Literal["EQUITY", "OPTION"] = "EQUITY"
    side: PaperOrderSide
    order_type: PaperOrderType
    quantity: int = Field(gt=0, le=10000)
    limit_price: float | None = Field(default=None, gt=0)
    estimated_price: float | None = Field(default=None, gt=0)
    option_expiry: str | None = None
    option_strike: float | None = Field(default=None, gt=0)
    option_type: Literal["CALL", "PUT"] | None = None
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=128)
    actor: GovernedActor

    @model_validator(mode="after")
    def validate_order(self):
        self.symbol = self.symbol.strip().upper()
        if self.order_type == PaperOrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        if self.instrument_type == "OPTION":
            if not self.option_expiry or self.option_strike is None or not self.option_type:
                raise ValueError(
                    "option_expiry, option_strike, and option_type are required "
                    "for OPTION orders"
                )
        return self


class PaperOrderCancelRequest(BaseModel):
    environment: Literal["PAPER", "SIMULATION"] = "PAPER"
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=128)
    actor: GovernedActor


class PaperOrderReplaceRequest(BaseModel):
    environment: Literal["PAPER", "SIMULATION"] = "PAPER"
    quantity: int | None = Field(default=None, gt=0, le=10000)
    limit_price: float | None = Field(default=None, gt=0)
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=128)
    actor: GovernedActor

    @model_validator(mode="after")
    def require_change(self):
        if self.quantity is None and self.limit_price is None:
            raise ValueError("quantity or limit_price must be provided")
        return self


class PaperOrderRecord(BaseModel):
    order_id: str
    environment: str
    symbol: str
    instrument_type: str
    side: PaperOrderSide
    order_type: PaperOrderType
    quantity: int
    limit_price: float | None = None
    estimated_price: float | None = None
    option_expiry: str | None = None
    option_strike: float | None = None
    option_type: str | None = None
    status: PaperOrderStatus
    reason: str
    actor_user_id: str
    actor_session_id: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    replaced_by_order_id: str | None = None
    rejection_reasons: list[str] = Field(default_factory=list)


class CommandDecision(BaseModel):
    allowed: bool
    status: str
    action: str
    order: PaperOrderRecord | None = None
    message: str
    policy_reasons: list[str] = Field(default_factory=list)
    idempotent_replay: bool = False


class PaperTradingSummary(BaseModel):
    environment: str = "PAPER"
    mode: str = "GOVERNED_PAPER_ONLY"
    live_trading_enabled: bool = False
    total_orders: int = 0
    open_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    gross_notional: float = 0.0


class PaperTradingState(BaseModel):
    generated_at: datetime
    summary: PaperTradingSummary
    orders: list[PaperOrderRecord] = Field(default_factory=list)
    permissions_required: list[str] = Field(default_factory=list)
    safety_notices: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_id: str
    occurred_at: datetime
    event_type: str
    action: str
    outcome: str
    actor_user_id: str
    actor_session_id: str
    environment: str
    resource_id: str | None = None
    reason: str
    detail: str
    idempotency_key: str
