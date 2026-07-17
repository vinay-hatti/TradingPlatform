from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OrderRouteCandidate:
    route_id: str
    broker: str
    environment: str
    account_id: str
    supports_equities: bool
    supports_options: bool
    supports_multi_leg_options: bool
    supports_live_trading: bool
    priority: int = 100
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderRoutingCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderRoutingDecision:
    valid: bool
    allowed: bool
    aggregate_id: str
    route_id: str | None
    broker: str | None
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    checks: tuple[OrderRoutingCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderWorkflowResult:
    valid: bool
    allowed: bool
    action: str
    aggregate_id: str
    state: str
    aggregate_version: int
    routing_decision: OrderRoutingDecision | None = None
    broker_result: Any = None
    persistence_result: Any = None
    recommendation: str = "REJECT"
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)
