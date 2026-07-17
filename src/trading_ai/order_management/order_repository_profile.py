from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .order_profile import CanonicalOrderAggregate, CanonicalOrderEvent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OrderRepositoryRecord:
    aggregate: CanonicalOrderAggregate
    persisted_version: int
    created_at: str
    updated_at: str
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderAuditEntry:
    sequence_number: int
    entry_id: str
    aggregate_id: str
    aggregate_version: int
    event_id: str
    event_type: str
    previous_hash: str
    entry_hash: str
    payload_hash: str
    recorded_at: str = field(default_factory=utc_now_iso)
    actor: str = "system"
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderPersistenceResult:
    valid: bool
    allowed: bool
    action: str
    aggregate_id: str
    expected_version: int | None
    actual_version: int | None
    persisted_version: int | None
    aggregate: CanonicalOrderAggregate | None = None
    event: CanonicalOrderEvent | None = None
    audit_entry: OrderAuditEntry | None = None
    recommendation: str = "REJECT"
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderJournalReplayResult:
    valid: bool
    allowed: bool
    aggregate_id: str
    event_count: int
    final_version: int
    final_state: str
    events: tuple[CanonicalOrderEvent, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
