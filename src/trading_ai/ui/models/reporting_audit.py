from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ReportArtifact(BaseModel):
    name: str
    category: str
    relative_path: str
    extension: str
    size_bytes: int
    modified_at: datetime
    age_seconds: float
    stale: bool
    sha256: str | None = None
    integrity_status: str = "NOT_VERIFIED"
    description: str = ""


class AuditEvent(BaseModel):
    event_id: str
    occurred_at: datetime
    event_type: str
    severity: str = "INFO"
    actor: str = "system"
    entity_type: str = "platform"
    entity_id: str | None = None
    action: str
    outcome: str = "UNKNOWN"
    message: str = ""
    source: str


class GovernanceEvidence(BaseModel):
    control: str
    status: str
    evidence_count: int = 0
    latest_evidence_at: datetime | None = None
    detail: str = ""


class ReportingAuditSummary(BaseModel):
    report_count: int = 0
    audit_event_count: int = 0
    critical_event_count: int = 0
    warning_event_count: int = 0
    stale_report_count: int = 0
    verified_report_count: int = 0
    failed_integrity_count: int = 0
    governance_pass_count: int = 0
    governance_warning_count: int = 0
    governance_fail_count: int = 0


class ReportingAuditResponse(BaseModel):
    generated_at: datetime
    available: bool
    source_detail: str
    summary: ReportingAuditSummary
    reports: list[ReportArtifact] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    governance: list[GovernanceEvidence] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
