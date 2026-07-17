from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalGovernancePolicy:
    require_runbook_for_production: bool = True
    require_dr_plan_for_production: bool = True
    require_compliance_evidence: bool = True
    require_owner_and_reviewer: bool = True
    maximum_runbook_age_days: int = 180
    maximum_dr_test_age_days: int = 90
    maximum_unresolved_critical_findings: int = 0
    minimum_compliance_score: float = 0.95
    minimum_dr_readiness_score: float = 0.95
    require_incident_escalation_path: bool = True
    require_backup_validation: bool = True
    require_restore_validation: bool = True
    require_rto_rpo: bool = True
    require_production_change_record: bool = True

    def validate(self) -> None:
        if self.maximum_runbook_age_days <= 0:
            raise ValueError("maximum_runbook_age_days must be positive")
        if self.maximum_dr_test_age_days <= 0:
            raise ValueError("maximum_dr_test_age_days must be positive")
        if self.maximum_unresolved_critical_findings < 0:
            raise ValueError(
                "maximum_unresolved_critical_findings cannot be negative"
            )
        for name, value in (
            ("minimum_compliance_score", self.minimum_compliance_score),
            ("minimum_dr_readiness_score", self.minimum_dr_readiness_score),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
