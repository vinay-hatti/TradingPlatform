from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class MetricPoint(BaseModel):
    name: str
    value: float
    unit: str = "count"
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: datetime


class HealthCheckResult(BaseModel):
    name: str
    status: HealthStatus
    required: bool = True
    detail: str
    latency_ms: float | None = None
    observed_at: datetime


class AlertRecord(BaseModel):
    alert_id: str
    rule_name: str
    severity: AlertSeverity
    status: str
    message: str
    source: str
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class ObservabilitySummary(BaseModel):
    service_status: HealthStatus
    readiness_status: HealthStatus
    liveness_status: HealthStatus
    metric_count: int
    active_alert_count: int
    critical_alert_count: int
    warning_alert_count: int
    structured_log_path: str


class ObservabilityState(BaseModel):
    generated_at: datetime
    summary: ObservabilitySummary
    metrics: list[MetricPoint] = Field(default_factory=list)
    health_checks: list[HealthCheckResult] = Field(default_factory=list)
    alerts: list[AlertRecord] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class AlertAcknowledgeRequest(BaseModel):
    actor: str
    reason: str = Field(min_length=5, max_length=500)
