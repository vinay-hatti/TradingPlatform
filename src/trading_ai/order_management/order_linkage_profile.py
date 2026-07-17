from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OrderLinkMember:
    aggregate_id: str
    role: str
    activation_state: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderGroupProfile:
    group_id: str
    group_type: str
    account_id: str
    root_aggregate_id: str
    members: tuple[OrderLinkMember, ...]
    state: str = "ACTIVE"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderLinkageCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderGroupDecision:
    valid: bool
    allowed: bool
    action: str
    group: OrderGroupProfile | None
    score: float
    grade: str
    severity: str
    recommendation: str
    checks: tuple[OrderLinkageCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderRecoveryCheckpoint:
    checkpoint_id: str
    aggregate_id: str
    aggregate_version: int
    workflow_action: str
    state: str
    broker_order_id: str | None = None
    route_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    completed_steps: tuple[str, ...] = ()
    pending_steps: tuple[str, ...] = ()
    retry_count: int = 0
    recoverable: bool = True
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class OrderGroupWorkflowResult:
    valid: bool
    allowed: bool
    action: str
    group_id: str | None
    aggregate_ids: tuple[str, ...]
    recommendation: str
    broker_results: tuple[Any, ...] = ()
    persistence_results: tuple[Any, ...] = ()
    recovery_checkpoint: OrderRecoveryCheckpoint | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
