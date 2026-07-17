from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PreTradeAccountProfile:
    account_id: str
    currency: str
    net_liquidation: float
    buying_power: float
    option_buying_power: float
    cash_balance: float = 0.0
    maintenance_requirement: float = 0.0
    excess_liquidity: float = 0.0
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreTradeRiskLeg:
    leg_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: float
    price: float | None
    multiplier: int = 1
    strike: float | None = None
    option_type: str | None = None
    expiration: str | None = None
    position_effect: str = "AUTO"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreTradeRiskRequest:
    aggregate_id: str
    client_order_id: str
    account_id: str
    order_type: str
    time_in_force: str
    legs: tuple[PreTradeRiskLeg, ...]
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_name: str | None = None
    route_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreTradeExposureProfile:
    gross_notional: float
    net_notional: float
    gross_premium: float
    net_premium: float
    maximum_loss: float | None
    maximum_profit: float | None
    total_contracts: int
    total_equity_quantity: float
    defined_risk: bool
    risk_classification: str
    buying_power_required: float
    order_pct_of_buying_power: float | None
    order_pct_of_net_liquidation: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreTradeRiskCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreTradeRiskDecision:
    valid: bool
    allowed: bool
    aggregate_id: str
    client_order_id: str
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    exposure: PreTradeExposureProfile | None = None
    account: PreTradeAccountProfile | None = None
    checks: tuple[PreTradeRiskCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
