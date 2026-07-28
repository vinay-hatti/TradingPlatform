from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BrokerOrderLifecycleSnapshot:
    aggregate_id: str
    broker_order_id: int
    symbol: str
    security_type: str
    side: str
    quantity: float
    status: str
    filled_quantity: float
    remaining_quantity: float
    average_fill_price: float
    submitted_at: str
    updated_at: str
    canonical_state: str = ""
    canonical_terminal_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerExecutionSnapshot:
    execution_id: str
    aggregate_id: str
    broker_order_id: int
    symbol: str
    security_type: str
    side: str
    quantity: float
    price: float
    commission: float
    currency: str
    exchange: str
    executed_at: str
    contract_id: int = 0
    permanent_id: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LifecycleAction:
    aggregate_id: str
    broker_order_id: int
    action: str
    reason: str
    allowed: bool
    confirmation_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperPositionProjection:
    position_id: str
    portfolio_id: str
    aggregate_id: str
    symbol: str
    security_type: str
    direction: str
    quantity: float
    average_entry_price: float
    total_commission: float
    currency: str
    opened_at: str
    last_execution_at: str
    execution_ids: tuple[str, ...]
    status: str = "OPEN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomatedLifecycleResult:
    milestone: int
    phase: int
    portfolio_id: str
    mode: str
    synchronization: dict[str, Any]
    orders: tuple[dict[str, Any], ...]
    actions: tuple[dict[str, Any], ...]
    cancellations: tuple[dict[str, Any], ...]
    positions: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    status: str
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
