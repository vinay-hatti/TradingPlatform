from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CertificationControl:
    control_id: str
    category: str
    title: str
    required: bool
    passed: bool
    score: float
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""


@dataclass(frozen=True)
class RunbookCertification:
    runbook_id: str
    name: str
    ready: bool
    score: float
    findings: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class DisasterRecoveryExercise:
    exercise_id: str
    plan_id: str
    scenario: str
    started_at: str
    completed_at: str
    target_rto_minutes: int
    observed_rto_minutes: float
    target_rpo_minutes: int
    observed_rpo_minutes: float
    backup_verified: bool
    restore_verified: bool
    failover_verified: bool
    failback_verified: bool
    evidence: tuple[str, ...] = ()
    notes: str = ""

    @property
    def rto_passed(self) -> bool:
        return self.observed_rto_minutes <= self.target_rto_minutes

    @property
    def rpo_passed(self) -> bool:
        return self.observed_rpo_minutes <= self.target_rpo_minutes

    @property
    def passed(self) -> bool:
        return all(
            (
                self.rto_passed,
                self.rpo_passed,
                self.backup_verified,
                self.restore_verified,
                self.failover_verified,
                self.failback_verified,
                bool(self.evidence),
            )
        )


@dataclass(frozen=True)
class MilestoneClosureSignOff:
    release_id: str
    release_version: str
    approved_by: tuple[str, ...]
    approval_roles: tuple[str, ...]
    decision: str
    comments: str
    signed_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ProductionReadinessCertification:
    project_name: str
    milestone: str
    phase: str
    release_version: str
    environment: str
    overall_score: float
    certified: bool
    certification_decision: str
    controls: tuple[CertificationControl, ...]
    runbooks: tuple[RunbookCertification, ...]
    dr_exercises: tuple[DisasterRecoveryExercise, ...]
    critical_findings: int
    high_findings: int
    sign_off: MilestoneClosureSignOff | None
    generated_at: str = field(default_factory=utc_now_iso)
