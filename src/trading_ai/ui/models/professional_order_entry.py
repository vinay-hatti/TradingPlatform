from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from trading_ai.ui.models.paper_commands import GovernedActor


class StrategyLeg(BaseModel):
    leg_id: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=20)
    option_expiry: str
    option_strike: float = Field(gt=0)
    option_type: Literal["CALL", "PUT"]
    side: Literal["BUY", "SELL"]
    ratio: int = Field(default=1, ge=1, le=20)
    bid: float = Field(default=0, ge=0)
    ask: float = Field(default=0, ge=0)
    delta: float = 0
    gamma: float = 0
    theta: float = 0
    vega: float = 0

    @model_validator(mode="after")
    def normalize(self):
        self.symbol = self.symbol.strip().upper()
        return self


class StrategyTicketRequest(BaseModel):
    environment: Literal["PAPER", "SIMULATION"] = "PAPER"
    account_id: str = Field(min_length=1, max_length=128)
    strategy_name: str = Field(min_length=1, max_length=120)
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    time_in_force: Literal["DAY", "GTC"] = "DAY"
    contracts: int = Field(default=1, ge=1, le=1000)
    net_limit_price: float | None = None
    underlying_price: float = Field(gt=0)
    account_equity: float = Field(gt=0)
    max_risk_pct: float = Field(default=0.02, gt=0, le=0.20)
    commission_per_contract: float = Field(default=0.65, ge=0, le=25)
    reason: str = Field(min_length=5, max_length=500)
    legs: list[StrategyLeg] = Field(min_length=1, max_length=8)
    actor: GovernedActor

    @model_validator(mode="after")
    def validate_ticket(self):
        symbols = {leg.symbol for leg in self.legs}
        expiries = {leg.option_expiry for leg in self.legs}
        if len(symbols) != 1:
            raise ValueError("All legs must use the same underlying symbol.")
        if self.order_type == "LIMIT" and self.net_limit_price is None:
            raise ValueError("net_limit_price is required for LIMIT orders.")
        if len(expiries) > 2:
            raise ValueError("A maximum of two expirations is supported.")
        return self


class StrategyRiskPreview(BaseModel):
    strategy_type: str
    contracts_requested: int
    contracts_recommended: int
    net_debit_credit: float
    estimated_commission: float
    estimated_margin: float
    maximum_loss: float | None
    maximum_profit: float | None
    breakevens: list[float]
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    risk_budget: float
    risk_budget_utilization_pct: float | None
    bounded_risk: bool
    warnings: list[str] = Field(default_factory=list)


class StrategyTicketRecord(BaseModel):
    ticket_id: str
    created_at: datetime
    updated_at: datetime
    status: Literal[
        "DRAFT", "PREVIEWED", "PENDING_APPROVAL", "APPROVED",
        "REJECTED", "SUBMITTED", "PARTIALLY_SUBMITTED"
    ]
    request: StrategyTicketRequest
    preview: StrategyRiskPreview
    requester_user_id: str
    approver_user_id: str | None = None
    approval_reason: str | None = None
    submitted_order_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    actor: GovernedActor


class SubmissionRequest(BaseModel):
    confirmation_token: str = Field(min_length=8, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=128)
    actor: GovernedActor
