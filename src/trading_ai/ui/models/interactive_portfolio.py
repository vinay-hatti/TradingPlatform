from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PortfolioPosition(BaseModel):
    position_id: str
    account_id: str = "paper-account"
    symbol: str
    instrument_type: Literal["EQUITY", "OPTION"] = "OPTION"
    quantity: float
    average_price: float = 0
    mark_price: float = 0
    multiplier: float = 100
    option_expiry: str | None = None
    option_strike: float | None = None
    option_type: Literal["CALL", "PUT"] | None = None
    delta: float = 0
    gamma: float = 0
    theta: float = 0
    vega: float = 0
    implied_volatility: float = 0
    underlying_price: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0


class PortfolioSummary(BaseModel):
    generated_at: datetime
    account_id: str
    total_market_value: float
    total_unrealized_pnl: float
    gross_exposure: float
    net_exposure: float
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    long_positions: int
    short_positions: int
    symbols: int
    positions: list[PortfolioPosition]


class ScenarioPoint(BaseModel):
    underlying_shock_pct: float
    volatility_shock_points: float
    days_forward: int
    estimated_pnl: float
    estimated_market_value: float
    delta_pnl: float
    gamma_pnl: float
    vega_pnl: float
    theta_pnl: float


class ScenarioRequest(BaseModel):
    account_id: str = "paper-account"
    underlying_shocks_pct: list[float] = Field(
        default=[-0.10, -0.05, 0, 0.05, 0.10], min_length=1, max_length=21
    )
    volatility_shocks_points: list[float] = Field(
        default=[-0.05, 0, 0.05], min_length=1, max_length=11
    )
    days_forward: list[int] = Field(default=[0, 1, 5], min_length=1, max_length=10)


class ExposureCell(BaseModel):
    symbol: str
    expiration: str
    delta: float
    gamma: float
    theta: float
    vega: float
    market_value: float
    unrealized_pnl: float


class RebalanceConstraint(BaseModel):
    max_abs_delta: float = Field(default=100, ge=0)
    max_abs_vega: float = Field(default=1000, ge=0)
    max_symbol_exposure_pct: float = Field(default=0.30, gt=0, le=1)
    account_equity: float = Field(default=100000, gt=0)


class RebalanceProposal(BaseModel):
    proposal_id: str
    created_at: datetime
    account_id: str
    status: Literal["PROPOSED"] = "PROPOSED"
    objective: str
    current_delta: float
    target_delta: float
    estimated_delta_change: float
    estimated_notional: float
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    rationale: list[str]
    warnings: list[str]
    phase3_handoff: dict
