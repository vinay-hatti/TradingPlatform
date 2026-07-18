from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PortfolioPosition(BaseModel):
    symbol: str
    strategy: str = "Unknown"
    direction: str = "UNKNOWN"
    quantity: float = 0.0
    entry_price: float | None = None
    current_price: float | None = None
    market_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    allocation_pct: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    risk_score: float | None = None
    status: str = "OPEN"
    source: str
    as_of: datetime


class PortfolioSummary(BaseModel):
    capital: float = 0.0
    cash: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    return_pct: float | None = None
    open_positions: int = 0
    winning_positions: int = 0
    losing_positions: int = 0


class RiskSnapshot(BaseModel):
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    largest_position_pct: float = 0.0
    top_three_concentration_pct: float = 0.0
    max_drawdown_pct: float | None = None
    value_at_risk: float | None = None
    expected_shortfall: float | None = None
    buying_power_utilization_pct: float | None = None
    risk_utilization_pct: float | None = None
    risk_level: str = "UNKNOWN"


class RiskLimit(BaseModel):
    name: str
    current_value: float | None = None
    limit_value: float | None = None
    utilization_pct: float | None = None
    status: str = "UNKNOWN"
    detail: str = ""


class PortfolioRiskResponse(BaseModel):
    generated_at: datetime
    available: bool
    stale: bool
    age_seconds: float | None = None
    source_detail: str
    summary: PortfolioSummary
    risk: RiskSnapshot
    positions: list[PortfolioPosition] = Field(default_factory=list)
    limits: list[RiskLimit] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
