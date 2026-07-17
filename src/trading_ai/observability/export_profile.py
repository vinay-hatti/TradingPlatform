from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AggregatedMetric:
    name: str
    metric_type: str
    labels: dict[str, str]
    sample_count: int
    value: float | None = None
    sum_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    buckets: dict[str, int] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    exemplar_trace_id: str | None = None
    exemplar_span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExportEnvelope:
    envelope_id: str
    signal_type: str
    payload: dict[str, Any]
    status: str = "PENDING"
    attempt_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_error: str | None = None


@dataclass(frozen=True)
class ExportBatchResult:
    signal_type: str
    attempted: int
    exported: int
    retained: int
    dropped: int
    success: bool
    error: str | None = None
    exported_at: str = field(default_factory=utc_now_iso)
