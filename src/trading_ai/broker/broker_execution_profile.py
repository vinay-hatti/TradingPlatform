from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .broker_order_profile import (
    BrokerOrderRequest,
    BrokerOrderValidationProfile,
)
from .broker_profile import BrokerReadinessProfile


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BrokerOrderStateProfile:
    broker: str
    broker_order_id: str
    client_order_id: str
    account_id: str
    status: str
    order: BrokerOrderRequest
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float | None = None
    replace_count: int = 0
    parent_broker_order_id: str | None = None
    root_broker_order_id: str | None = None
    submitted_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    canceled_at: str | None = None
    filled_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerExecutionCheckProfile:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerOrderExecutionResult:
    valid: bool
    allowed: bool
    action: str
    status: str
    broker: str
    client_order_id: str
    broker_order_id: str | None
    idempotency_key: str | None
    replayed: bool = False
    score: float = 0.0
    grade: str = "F"
    severity: str = "CRITICAL"
    recommendation: str = "REJECT"
    order_state: BrokerOrderStateProfile | None = None
    validation: BrokerOrderValidationProfile | None = None
    readiness: BrokerReadinessProfile | None = None
    checks: tuple[BrokerExecutionCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrokerCancelRequest:
    broker_order_id: str
    account_id: str
    client_request_id: str
    idempotency_key: str
    reason: str = "USER_REQUEST"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerReplaceRequest:
    broker_order_id: str
    replacement_order: BrokerOrderRequest
    client_request_id: str
    idempotency_key: str
    reason: str = "USER_REQUEST"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdempotencyRecordProfile:
    key: str
    action: str
    request_hash: str
    broker_order_id: str | None
    client_order_id: str | None
    status: str
    result: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
