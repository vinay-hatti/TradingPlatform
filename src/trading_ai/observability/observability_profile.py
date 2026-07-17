from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ObservabilityContext:
    service_name: str
    environment: str
    instance_id: str | None = None
    component: str | None = None
    operation: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredLogRecord:
    level: str
    message: str
    context: ObservabilityContext
    timestamp: str = field(default_factory=utc_now_iso)
    event_name: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    metric_type: str
    description: str
    unit: str = "1"
    label_names: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricSample:
    name: str
    metric_type: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)
    exemplar_trace_id: str | None = None
    exemplar_span_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpanEvent:
    name: str
    timestamp: str = field(default_factory=utc_now_iso)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    service_name: str
    environment: str
    parent_span_id: str | None = None
    kind: str = "INTERNAL"
    status: str = "UNSET"
    sampled: bool = True
    start_time: str = field(default_factory=utc_now_iso)
    end_time: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: tuple[SpanEvent, ...] = ()
    baggage: dict[str, str] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    root_span_id: str
    service_name: str
    environment: str
    spans: tuple[TraceSpan, ...]
    started_at: str
    completed_at: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
