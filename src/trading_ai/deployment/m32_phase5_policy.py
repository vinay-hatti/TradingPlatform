from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionReadinessCertificationPolicy:
    minimum_overall_score: float = 0.98
    minimum_runbook_score: float = 1.0
    minimum_dr_exercise_pass_rate: float = 1.0
    maximum_critical_findings: int = 0
    maximum_high_findings: int = 0
    require_sign_off: bool = True
    require_approved_sign_off: bool = True
    require_all_required_controls: bool = True
    require_backup_restore_evidence: bool = True
    require_rto_rpo_validation: bool = True
    require_live_trading_disabled: bool = True

    def validate(self) -> None:
        for name, value in (
            ("minimum_overall_score", self.minimum_overall_score),
            ("minimum_runbook_score", self.minimum_runbook_score),
            (
                "minimum_dr_exercise_pass_rate",
                self.minimum_dr_exercise_pass_rate,
            ),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.maximum_critical_findings < 0:
            raise ValueError("maximum_critical_findings cannot be negative")
        if self.maximum_high_findings < 0:
            raise ValueError("maximum_high_findings cannot be negative")
