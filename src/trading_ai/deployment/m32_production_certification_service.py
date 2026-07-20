from __future__ import annotations

from typing import Any

from .disaster_recovery_service import DisasterRecoveryService
from .m32_phase5_policy import ProductionReadinessCertificationPolicy
from .m32_phase5_profile import (
    CertificationControl,
    DisasterRecoveryExercise,
    MilestoneClosureSignOff,
    ProductionReadinessCertification,
    RunbookCertification,
)


class ProductionReadinessCertificationService:
    WEIGHTS = {
        "SOFTWARE": 0.20,
        "DEPLOYMENT": 0.15,
        "OBSERVABILITY": 0.15,
        "OPERATIONAL_GOVERNANCE": 0.15,
        "RUNBOOKS": 0.10,
        "DISASTER_RECOVERY": 0.15,
        "SECURITY_AND_RISK": 0.10,
    }

    def __init__(
        self,
        policy: ProductionReadinessCertificationPolicy | None = None,
        dr_service: DisasterRecoveryService | None = None,
    ) -> None:
        self.policy = policy or ProductionReadinessCertificationPolicy()
        self.policy.validate()
        self.dr_service = dr_service or DisasterRecoveryService()

    def certify(
        self,
        *,
        project_name: str,
        release_version: str,
        environment: str,
        controls: tuple[CertificationControl, ...],
        runbooks: tuple[RunbookCertification, ...],
        dr_plan: Any,
        dr_exercises: tuple[DisasterRecoveryExercise, ...],
        sign_off: MilestoneClosureSignOff | None,
        live_trading_enabled: bool,
    ) -> ProductionReadinessCertification:
        dr_plan_ready, dr_plan_score, dr_findings = self.dr_service.evaluate(
            dr_plan
        )

        category_values: dict[str, list[float]] = {}
        for control in controls:
            category_values.setdefault(control.category.upper(), []).append(
                max(0.0, min(1.0, control.score))
            )

        runbook_score = (
            sum(item.score for item in runbooks) / len(runbooks)
            if runbooks
            else 0.0
        )
        category_values.setdefault("RUNBOOKS", []).append(runbook_score)

        dr_exercise_rate = (
            sum(1.0 if item.passed else 0.0 for item in dr_exercises)
            / len(dr_exercises)
            if dr_exercises
            else 0.0
        )
        category_values.setdefault("DISASTER_RECOVERY", []).extend(
            (dr_plan_score, dr_exercise_rate)
        )

        weighted = 0.0
        total_weight = 0.0
        for category, weight in self.WEIGHTS.items():
            values = category_values.get(category, ())
            score = sum(values) / len(values) if values else 0.0
            weighted += score * weight
            total_weight += weight
        overall_score = weighted / total_weight if total_weight else 0.0

        critical = sum(
            control.required
            and not control.passed
            and str(control.evidence.get("severity", "")).upper()
            == "CRITICAL"
            for control in controls
        ) + sum(
            finding.severity.upper() == "CRITICAL" for finding in dr_findings
        )
        high = sum(
            control.required
            and not control.passed
            and str(control.evidence.get("severity", "")).upper() == "HIGH"
            for control in controls
        ) + sum(finding.severity.upper() == "HIGH" for finding in dr_findings)

        required_controls_pass = all(
            (not item.required) or item.passed for item in controls
        )
        runbooks_pass = bool(runbooks) and all(item.ready for item in runbooks)
        dr_exercises_pass = (
            bool(dr_exercises)
            and dr_exercise_rate
            >= self.policy.minimum_dr_exercise_pass_rate
        )
        sign_off_pass = (
            sign_off is not None
            and sign_off.decision.upper() == "APPROVED"
        )
        live_trading_pass = (
            not self.policy.require_live_trading_disabled
            or not live_trading_enabled
        )

        certified = (
            overall_score >= self.policy.minimum_overall_score
            and (
                not self.policy.require_all_required_controls
                or required_controls_pass
            )
            and runbook_score >= self.policy.minimum_runbook_score
            and runbooks_pass
            and dr_plan_ready
            and dr_exercises_pass
            and critical <= self.policy.maximum_critical_findings
            and high <= self.policy.maximum_high_findings
            and (not self.policy.require_sign_off or sign_off is not None)
            and (
                not self.policy.require_approved_sign_off
                or sign_off_pass
            )
            and live_trading_pass
        )

        return ProductionReadinessCertification(
            project_name=project_name,
            milestone="Milestone 32",
            phase="Phase 5",
            release_version=release_version,
            environment=environment,
            overall_score=overall_score,
            certified=certified,
            certification_decision=(
                "MILESTONE_32_CERTIFIED_AND_CLOSED"
                if certified
                else "BLOCK_MILESTONE_32_CLOSURE"
            ),
            controls=controls,
            runbooks=runbooks,
            dr_exercises=dr_exercises,
            critical_findings=critical,
            high_findings=high,
            sign_off=sign_off,
        )
