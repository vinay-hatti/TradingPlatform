from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PortfolioPositionInput:
    position_id: str
    symbol: str
    security_type: str
    direction: str
    quantity: float
    average_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    sector: str = "UNKNOWN"
    industry: str = "UNKNOWN"
    beta: float = 1.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    multiplier: float = 1.0
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioState:
    portfolio_id: str
    cash: float
    buying_power: float
    net_liquidation_value: float
    gross_market_value: float
    net_market_value: float
    gross_exposure_pct: float
    net_exposure_pct: float
    capital_utilization_pct: float
    margin_utilization_pct: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    open_position_count: int
    option_contract_count: int
    long_market_value: float
    short_market_value: float
    portfolio_beta: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    delta_notional: float
    gamma_notional: float
    vega_notional: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioExposureBucket:
    key: str
    market_value: float
    absolute_market_value: float
    capital_pct: float
    net_pct: float
    position_count: int


@dataclass(frozen=True)
class PortfolioRiskBreach:
    code: str
    severity: str
    actual: float
    limit: float
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioRecommendation:
    code: str
    priority: str
    action: str
    rationale: str
    target: str
    estimated_impact: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioHealthScore:
    overall: float
    liquidity: float
    diversification: float
    greeks: float
    risk: float
    drawdown: float
    execution: float
    grade: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomatedPortfolioManagementResult:
    milestone: int
    phase: int
    portfolio_id: str
    state: dict[str, Any]
    greeks: dict[str, Any]
    exposure_by_symbol: tuple[dict[str, Any], ...]
    exposure_by_sector: tuple[dict[str, Any], ...]
    exposure_by_industry: tuple[dict[str, Any], ...]
    exposure_by_asset_class: tuple[dict[str, Any], ...]
    risk_breaches: tuple[dict[str, Any], ...]
    recommendations: tuple[dict[str, Any], ...]
    health: dict[str, Any]
    daily_snapshot: dict[str, Any]
    status: str
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
