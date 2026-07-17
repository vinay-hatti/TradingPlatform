from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BrokerOrderStatusEvent:
    broker: str
    broker_order_id: str
    client_order_id: str
    account_id: str
    status: str
    event_timestamp: str
    sequence_number: int | None = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerFillEvent:
    broker: str
    broker_order_id: str
    client_order_id: str
    account_id: str
    execution_id: str
    leg_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    event_timestamp: str
    sequence_number: int | None = None
    commission: float = 0.0
    fees: float = 0.0
    liquidity: str | None = None
    exchange: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerCommissionProfile:
    execution_id: str
    commission: float
    fees: float
    total_cost: float
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerOrderExecutionSummary:
    broker_order_id: str
    client_order_id: str
    status: str
    ordered_quantity: float
    filled_quantity: float
    remaining_quantity: float
    average_fill_price: float | None
    gross_notional: float
    commission: float
    fees: float
    net_cash_flow: float
    fill_count: int
    last_event_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerPositionProfile:
    broker: str
    account_id: str
    symbol: str
    asset_class: str
    quantity: float
    average_cost: float
    market_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float = 0.0
    multiplier: int = 1
    as_of: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionReconciliationCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionReconciliationProfile:
    valid: bool
    allowed: bool
    account_id: str
    symbol: str
    score: float
    grade: str
    severity: str
    recommendation: str
    broker_position: BrokerPositionProfile | None
    platform_position: BrokerPositionProfile | None
    quantity_difference: float | None
    average_cost_difference: float | None
    average_cost_difference_pct: float | None
    checks: tuple[PositionReconciliationCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class BrokerReconciliationSummary:
    valid: bool
    allowed: bool
    order_count: int
    fill_count: int
    position_count: int
    matched_position_count: int
    rejected_position_count: int
    score: float
    grade: str
    severity: str
    recommendation: str
    order_summaries: tuple[BrokerOrderExecutionSummary, ...] = ()
    position_profiles: tuple[PositionReconciliationProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
