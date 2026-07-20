from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from trading_ai.deployment.m32_dr_exercise_service import (
    DisasterRecoveryExerciseService,
)
from trading_ai.deployment.m32_phase5_profile import (
    CertificationControl,
    MilestoneClosureSignOff,
    RunbookCertification,
)
from trading_ai.deployment.m32_production_certification_service import (
    ProductionReadinessCertificationService,
)


class PassingDRService:
    def evaluate(self, plan):
        return True, 1.0, ()


def main():
    now = datetime.now(timezone.utc)
    plan = SimpleNamespace(
        dr_plan_id="test-dr",
        rto_minutes=30,
        rpo_minutes=5,
    )
    exercise = DisasterRecoveryExerciseService().record(
        exercise_id="exercise-1",
        plan=plan,
        scenario="Restore paper state",
        started_at=now,
        completed_at=now + timedelta(minutes=10),
        observed_rpo_minutes=2,
        backup_verified=True,
        restore_verified=True,
        failover_verified=True,
        failback_verified=True,
        evidence=("backup", "restore", "reconciliation"),
    )
    assert exercise.passed
    assert exercise.rto_passed
    assert exercise.rpo_passed

    controls = tuple(
        CertificationControl(
            control_id=f"control-{index}",
            category=category,
            title=category,
            required=True,
            passed=True,
            score=1.0,
            evidence={"severity": "CRITICAL"},
        )
        for index, category in enumerate(
            (
                "SOFTWARE",
                "DEPLOYMENT",
                "OBSERVABILITY",
                "OPERATIONAL_GOVERNANCE",
                "SECURITY_AND_RISK",
            ),
            start=1,
        )
    )
    runbooks = (
        RunbookCertification(
            runbook_id="runbook-1",
            name="Production Operations",
            ready=True,
            score=1.0,
        ),
    )
    sign_off = MilestoneClosureSignOff(
        release_id="release-32.5",
        release_version="32.5.0",
        approved_by=("owner", "risk", "operations"),
        approval_roles=("OWNER", "RISK", "OPERATIONS"),
        decision="APPROVED",
        comments="Approved for governed paper operation.",
    )

    result = ProductionReadinessCertificationService(
        dr_service=PassingDRService()
    ).certify(
        project_name="Trading AI Platform",
        release_version="32.5.0",
        environment="PAPER",
        controls=controls,
        runbooks=runbooks,
        dr_plan=plan,
        dr_exercises=(exercise,),
        sign_off=sign_off,
        live_trading_enabled=False,
    )
    assert result.certified
    assert result.overall_score == 1.0
    assert result.certification_decision == "MILESTONE_32_CERTIFIED_AND_CLOSED"

    blocked = ProductionReadinessCertificationService(
        dr_service=PassingDRService()
    ).certify(
        project_name="Trading AI Platform",
        release_version="32.5.0",
        environment="PRODUCTION",
        controls=controls,
        runbooks=runbooks,
        dr_plan=plan,
        dr_exercises=(exercise,),
        sign_off=sign_off,
        live_trading_enabled=True,
    )
    assert not blocked.certified
    assert blocked.certification_decision == "BLOCK_MILESTONE_32_CLOSURE"

    print(
        "All Milestone 32 Phase 5 Production Readiness Certification, "
        "Operational Runbooks, Disaster Recovery Exercises, and Milestone "
        "Closure assertions passed."
    )


if __name__ == "__main__":
    main()
