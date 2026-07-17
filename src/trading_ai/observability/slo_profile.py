from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SLODefinition:
    slo_id: str
    service_name: str
    environment: str
    indicator_type: str
    target: float
    metric_name: str
    good_when: str = "GREATER_THAN_OR_EQUAL"
    threshold: float | None = None
    window_seconds: float = 3600.0
    description: str = ""
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SLOEvaluation:
    slo_id: str
    service_name: str
    environment: str
    indicator_type: str
    target: float
    observed: float
    compliant: bool
    sample_count: int
    good_events: int
    total_events: int
    window_seconds: float
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ErrorBudgetEvaluation:
    slo_id: str
    allowed_bad_fraction: float
    observed_bad_fraction: float
    consumed_fraction: float
    remaining_fraction: float
    burn_rate: float
    exhausted: bool
    fast_burn: bool
    slow_burn: bool
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ObservabilityAlert:
    alert_id: str
    rule_id: str
    service_name: str
    environment: str
    severity: str
    status: str
    summary: str
    fingerprint: str
    occurrence_count: int = 1
    first_seen_at: str = field(default_factory=utc_now_iso)
    last_seen_at: str = field(default_factory=utc_now_iso)
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetentionResult:
    telemetry_type: str
    scanned: int
    retained: int
    deleted: int
    archived: int
    compliant: bool
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)
