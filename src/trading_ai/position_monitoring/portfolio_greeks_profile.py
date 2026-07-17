from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RealTimePositionGreeks:
    position_id: str
    symbol: str
    underlying_symbol: str
    quantity: float
    multiplier: int
    side: str
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    underlying_price: float
    implied_volatility: float | None = None
    option_price: float | None = None
    timestamp: str = field(default_factory=utc_now_iso)
    source: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GreeksExposureSurfacePoint:
    surface_id: str
    underlying_symbol: str
    underlying_shock_pct: float
    volatility_shock: float
    time_decay_days: int
    projected_pnl: float
    projected_loss: float
    delta_pnl: float
    gamma_pnl: float
    vega_pnl: float
    theta_pnl: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnderlyingGreeksExposure:
    underlying_symbol: str
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    scenario_loss: float
    surface_points: tuple[GreeksExposureSurfacePoint, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioGreeksRiskState:
    account_id: str
    snapshot_id: str
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    worst_scenario_id: str | None
    worst_scenario_loss: float
    worst_scenario_loss_pct_of_equity: float | None
    by_underlying: tuple[UnderlyingGreeksExposure, ...] = ()
    surface_points: tuple[GreeksExposureSurfacePoint, ...] = ()
    stale_greeks_count: int = 0
    missing_greeks_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioGreeksCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioGreeksDecision:
    valid: bool
    allowed: bool
    account_id: str
    snapshot_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    risk_state: PortfolioGreeksRiskState | None = None
    checks: tuple[PortfolioGreeksCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
