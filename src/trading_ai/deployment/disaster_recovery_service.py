from __future__ import annotations

from datetime import datetime, timezone

from .operational_governance_policy import OperationalGovernancePolicy
from .operational_governance_profile import (
    DisasterRecoveryPlan,
    GovernanceFinding,
)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class DisasterRecoveryService:
    def __init__(
        self,
        policy: OperationalGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalGovernancePolicy()
        self.policy.validate()

    def evaluate(
        self,
        plan: DisasterRecoveryPlan | None,
        *,
        as_of: datetime | None = None,
    ) -> tuple[bool, float, tuple[GovernanceFinding, ...]]:
        findings: list[GovernanceFinding] = []
        if plan is None:
            findings.append(
                GovernanceFinding(
                    finding_id="dr-plan-missing",
                    category="DISASTER_RECOVERY",
                    severity="CRITICAL",
                    status="OPEN",
                    summary="Disaster recovery plan is missing.",
                    recommendation="Create and test a disaster recovery plan.",
                )
            )
            return False, 0.0, tuple(findings)

        checks: list[bool] = []
        now = as_of or datetime.now(timezone.utc)

        for key, present, severity, message, recommendation in (
            (
                "owner",
                bool(plan.owner and plan.reviewer),
                "HIGH",
                "DR owner or reviewer is missing.",
                "Assign accountable DR ownership and review.",
            ),
            (
                "regions",
                bool(plan.primary_region and plan.recovery_region),
                "CRITICAL",
                "Primary or recovery region is missing.",
                "Define primary and recovery locations.",
            ),
            (
                "procedures",
                bool(
                    plan.restore_procedure
                    and plan.failover_procedure
                    and plan.failback_procedure
                ),
                "CRITICAL",
                "Restore, failover, or failback procedure is missing.",
                "Document all recovery procedures.",
            ),
            (
                "rto-rpo",
                plan.rto_minutes > 0 and plan.rpo_minutes >= 0,
                "CRITICAL",
                "RTO or RPO is invalid.",
                "Define approved RTO and RPO targets.",
            ),
            (
                "backup",
                plan.backup_validated,
                "CRITICAL",
                "Backup validation has not passed.",
                "Validate backup integrity.",
            ),
            (
                "restore",
                plan.restore_validated,
                "CRITICAL",
                "Restore validation has not passed.",
                "Perform and document a restore test.",
            ),
        ):
            checks.append(present)
            if not present:
                findings.append(
                    GovernanceFinding(
                        finding_id=f"dr-{key}",
                        category="DISASTER_RECOVERY",
                        severity=severity,
                        status="OPEN",
                        summary=message,
                        recommendation=recommendation,
                    )
                )

        age_days = (now - _parse(plan.last_tested_at)).days
        recent = age_days <= self.policy.maximum_dr_test_age_days
        checks.append(recent)
        if not recent:
            findings.append(
                GovernanceFinding(
                    finding_id="dr-test-stale",
                    category="DISASTER_RECOVERY",
                    severity="HIGH",
                    status="OPEN",
                    summary=f"DR test is {age_days} days old.",
                    recommendation="Run a new disaster recovery exercise.",
                )
            )

        evidence = bool(plan.test_evidence)
        checks.append(evidence)
        if not evidence:
            findings.append(
                GovernanceFinding(
                    finding_id="dr-evidence",
                    category="DISASTER_RECOVERY",
                    severity="HIGH",
                    status="OPEN",
                    summary="DR test evidence is missing.",
                    recommendation="Attach test logs and recovery evidence.",
                )
            )

        score = sum(checks) / len(checks)
        ready = (
            all(checks)
            and score >= self.policy.minimum_dr_readiness_score
        )
        return ready, score, tuple(findings)
