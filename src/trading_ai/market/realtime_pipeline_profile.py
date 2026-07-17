from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DispatchedMarketEvent:
    event_id: str
    event_type: str
    symbol: str
    provider: str
    sequence_number: int | None
    received_at: str
    accepted: bool
    payload: Any = None
    quality: Any = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineSubscriberProfile:
    subscriber_id: str
    event_types: tuple[str, ...]
    symbols: tuple[str, ...]
    active: bool = True
    delivered_count: int = 0
    error_count: int = 0
    last_delivery_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineHealthProfile:
    valid: bool
    allowed: bool
    state: str
    score: float
    grade: str
    severity: str
    recommendation: str
    received_count: int
    accepted_count: int
    rejected_count: int
    quote_count: int
    trade_count: int
    dispatch_error_count: int
    sequence_gap_count: int
    out_of_order_count: int
    subscriber_count: int
    last_event_at: str | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class PaperStreamEventProfile:
    event_type: str
    symbol: str
    payload: dict[str, Any]
    sequence_number: int
    provider: str = "paper"
    emitted_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
