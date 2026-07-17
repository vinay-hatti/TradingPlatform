from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from .pretrade_risk_profile import PreTradeAccountProfile, PreTradeRiskRequest

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class PortfolioPositionProfile:
    account_id: str
    symbol: str
    underlying_symbol: str
    asset_class: str
    sector: str | None
    quantity: float
    average_cost: float
    market_price: float
    multiplier: int = 1
    market_value: float | None = None
    signed_exposure: float | None = None
    buying_power_usage: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PositionLimitProfile:
    symbol: str
    asset_class: str
    maximum_long_quantity: float | None = None
    maximum_short_quantity: float | None = None
    maximum_absolute_quantity: float | None = None
    maximum_notional: float | None = None
    maximum_order_quantity: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PortfolioSnapshotProfile:
    account: PreTradeAccountProfile
    positions: tuple[PortfolioPositionProfile, ...]
    position_limits: tuple[PositionLimitProfile, ...] = ()
    as_of: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SymbolExposureProfile:
    symbol: str
    sector: str | None
    asset_class: str
    current_quantity: float
    projected_quantity: float
    current_exposure: float
    order_exposure: float
    projected_exposure: float
    pct_of_net_liquidation: float | None
    new_position: bool
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SectorExposureProfile:
    sector: str
    current_exposure: float
    order_exposure: float
    projected_exposure: float
    pct_of_net_liquidation: float | None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PortfolioExposureProfile:
    current_gross_exposure: float
    projected_gross_exposure: float
    current_net_exposure: float
    projected_net_exposure: float
    current_buying_power_usage: float
    projected_buying_power_usage: float
    current_buying_power_utilization: float | None
    projected_buying_power_utilization: float | None
    projected_buying_power_remaining: float
    projected_excess_liquidity: float
    current_open_positions: int
    projected_open_positions: int
    new_positions: int
    symbols: tuple[SymbolExposureProfile, ...] = ()
    sectors: tuple[SectorExposureProfile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PortfolioRiskCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PortfolioRiskDecision:
    valid: bool
    allowed: bool
    aggregate_id: str
    client_order_id: str
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    exposure: PortfolioExposureProfile | None = None
    snapshot: PortfolioSnapshotProfile | None = None
    order: PreTradeRiskRequest | None = None
    checks: tuple[PortfolioRiskCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
