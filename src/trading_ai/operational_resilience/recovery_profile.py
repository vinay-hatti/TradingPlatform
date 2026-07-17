from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class RecoveryAction:
    action_id: str
    action_type: str
    service_name: str
    dependency_name: str | None = None
    requested_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    status: str = "PENDING"
    attempt_number: int = 1
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ServiceRestartRecord:
    restart_id: str
    service_name: str
    instance_id: str
    environment: str
    reason: str
    requested_by: str
    approved: bool
    status: str
    critical: bool
    requested_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    failure_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    title: str
    service_name: str
    environment: str
    severity: str
    status: str = "OPEN"
    assigned_role: str = "ON_CALL_OPERATIONS"
    source: str = "automatic-recovery"
    opened_at: str = field(default_factory=utc_now_iso)
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolution_note: str | None = None
    recovery_workflow_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RecoveryAuditEntry:
    audit_id: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    outcome: str
    timestamp: str = field(default_factory=utc_now_iso)
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RecoveryWorkflowState:
    workflow_id: str
    service_name: str
    instance_id: str
    environment: str
    trigger: str
    status: str
    current_step: str
    attempt_count: int
    actions: tuple[RecoveryAction, ...] = ()
    restart_record: ServiceRestartRecord | None = None
    incident: IncidentRecord | None = None
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    version: int = 1
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class RecoveryDecision:
    valid: bool
    allowed: bool
    workflow_id: str
    service_name: str
    recommendation: str
    state: RecoveryWorkflowState | None = None
    incident: IncidentRecord | None = None
    audit_entries: tuple[RecoveryAuditEntry, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
