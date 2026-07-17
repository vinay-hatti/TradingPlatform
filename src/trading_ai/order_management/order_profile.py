from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class CanonicalOrderLeg:
    leg_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: float
    position_effect: str = "AUTO"
    ratio: int = 1
    broker_symbol: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CanonicalOrderCommand:
    command_id: str
    command_type: str
    aggregate_id: str
    client_order_id: str
    account_id: str
    idempotency_key: str
    order_type: str
    time_in_force: str
    legs: tuple[CanonicalOrderLeg, ...]
    limit_price: float | None = None
    stop_price: float | None = None
    outside_regular_hours: bool = False
    strategy_name: str | None = None
    reason: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    issued_at: str = field(default_factory=utc_now_iso)

@dataclass(frozen=True)
class CanonicalOrderEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    client_order_id: str
    account_id: str
    event_timestamp: str
    previous_state: str
    new_state: str
    broker_order_id: str | None = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float | None = None
    reason: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CanonicalOrderAggregate:
    aggregate_id: str
    client_order_id: str
    account_id: str
    idempotency_key: str
    order_type: str
    time_in_force: str
    legs: tuple[CanonicalOrderLeg, ...]
    state: str
    version: int
    total_quantity: float
    filled_quantity: float
    remaining_quantity: float
    average_fill_price: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    outside_regular_hours: bool = False
    strategy_name: str | None = None
    broker_order_id: str | None = None
    parent_aggregate_id: str | None = None
    root_aggregate_id: str | None = None
    replace_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    terminal_at: str | None = None
    last_event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class OrderTransitionCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class OrderTransitionResult:
    valid: bool
    allowed: bool
    action: str
    aggregate: CanonicalOrderAggregate | None
    event: CanonicalOrderEvent | None
    score: float
    grade: str
    severity: str
    recommendation: str
    checks: tuple[OrderTransitionCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
