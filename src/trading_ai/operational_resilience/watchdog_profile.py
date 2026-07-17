from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class HealthAlert:
    alert_id: str
    fingerprint: str
    service_name: str
    environment: str
    severity: str
    title: str
    message: str
    channels: tuple[str, ...]
    status: str = "PENDING"
    occurrence_count: int = 1
    first_detected_at: str = field(default_factory=utc_now_iso)
    last_detected_at: str = field(default_factory=utc_now_iso)
    sent_at: str | None = None
    incident_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IncidentEscalation:
    escalation_id: str
    incident_id: str
    level: int
    target_role: str
    reason: str
    status: str = "PENDING"
    created_at: str = field(default_factory=utc_now_iso)
    due_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class WatchdogCycleState:
    cycle_id: str
    environment: str
    sequence_number: int
    status: str
    recommendation: str
    health_registry_id: str | None = None
    health_allowed: bool | None = None
    health_score: float | None = None
    alert_count: int = 0
    incident_count: int = 0
    escalation_count: int = 0
    recovery_count: int = 0
    failed_stage: str | None = None
    error: str | None = None
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class WatchdogDecision:
    valid: bool
    allowed: bool
    environment: str
    cycle_id: str
    recommendation: str
    cycle_state: WatchdogCycleState
    alerts: tuple[HealthAlert, ...] = ()
    escalations: tuple[IncidentEscalation, ...] = ()
    recovery_workflow_ids: tuple[str, ...] = ()
    incident_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
