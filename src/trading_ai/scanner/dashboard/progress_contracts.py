from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProgressEventType(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    SYMBOL_COMPLETED = "SYMBOL_COMPLETED"
    SYMBOL_FAILED = "SYMBOL_FAILED"
    SYMBOL_SKIPPED = "SYMBOL_SKIPPED"
    CHECKPOINT = "CHECKPOINT"
    SCAN_COMPLETED = "SCAN_COMPLETED"


@dataclass(frozen=True)
class ScanProgressEvent:
    event_type: ProgressEventType
    symbol: str | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    processed_count: int | None = None
    completed_count: int | None = None
    failed_count: int | None = None
    skipped_count: int | None = None
    elapsed_seconds: float | None = None
    message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgressCheckpoint:
    session_id: str
    universe_size: int
    completed_count: int
    failed_count: int
    skipped_count: int
    elapsed_seconds: float
    last_symbol: str | None
    last_event_at: datetime
    sequence: int


@dataclass(frozen=True)
class ProgressHealth:
    healthy: bool
    stale: bool
    seconds_since_last_event: float
    reason: str | None = None
