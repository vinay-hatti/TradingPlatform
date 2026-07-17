from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunbookStep:
    sequence: int
    title: str
    action: str
    validation: str
    rollback_action: str = ""
    owner_role: str = ""
    estimated_minutes: int = 0


@dataclass(frozen=True)
class OperationalRunbook:
    runbook_id: str
    name: str
    service_name: str
    environment: str
    owner: str
    reviewer: str
    version: str
    last_reviewed_at: str
    escalation_path: tuple[str, ...]
    prerequisites: tuple[str, ...]
    steps: tuple[RunbookStep, ...]
    recovery_steps: tuple[RunbookStep, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DisasterRecoveryPlan:
    dr_plan_id: str
    service_name: str
    environment: str
    owner: str
    reviewer: str
    primary_region: str
    recovery_region: str
    rto_minutes: int
    rpo_minutes: int
    backup_strategy: str
    restore_procedure: str
    failover_procedure: str
    failback_procedure: str
    last_tested_at: str
    backup_validated: bool
    restore_validated: bool
    dependencies: tuple[str, ...] = ()
    test_evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComplianceControl:
    control_id: str
    framework: str
    title: str
    description: str
    severity: str
    required: bool = True
    evidence_types: tuple[str, ...] = ()
    owner_role: str = ""


@dataclass(frozen=True)
class ComplianceEvidence:
    control_id: str
    evidence_id: str
    evidence_type: str
    location: str
    collected_at: str
    collected_by: str
    valid: bool
    notes: str = ""


@dataclass(frozen=True)
class GovernanceFinding:
    finding_id: str
    category: str
    severity: str
    status: str
    summary: str
    recommendation: str
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class OperationalGovernanceResult:
    service_name: str
    environment: str
    runbook_ready: bool
    dr_ready: bool
    compliance_ready: bool
    production_governance_ready: bool
    runbook_score: float
    dr_score: float
    compliance_score: float
    findings: tuple[GovernanceFinding, ...]
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)
