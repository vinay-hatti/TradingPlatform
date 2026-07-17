from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .operational_governance_policy import OperationalGovernancePolicy
from .operational_governance_profile import GovernanceFinding


@dataclass(frozen=True)
class ProductionChangeRecord:
    change_id: str
    deployment_id: str
    release_id: str
    environment: str
    owner: str
    approver: str
    reason: str
    risk_level: str
    implementation_window: str
    rollback_plan_id: str
    readiness_result_id: str
    emergency: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProductionGovernanceService:
    def __init__(
        self,
        policy: OperationalGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalGovernancePolicy()
        self.policy.validate()

    def evaluate(
        self,
        *,
        environment: str,
        change_record: ProductionChangeRecord | None,
        release_ready: bool,
        deployment_approved: bool,
        rollback_ready: bool,
        observability_ready: bool,
    ) -> tuple[bool, tuple[GovernanceFinding, ...]]:
        findings: list[GovernanceFinding] = []

        if environment.upper() != "PRODUCTION":
            return True, ()

        checks = {
            "change-record": change_record is not None,
            "release-ready": release_ready,
            "deployment-approved": deployment_approved,
            "rollback-ready": rollback_ready,
            "observability-ready": observability_ready,
        }

        messages = {
            "change-record": (
                "Production change record is missing.",
                "Create and approve the production change record.",
            ),
            "release-ready": (
                "Release readiness validation has not passed.",
                "Resolve all blocking release-readiness findings.",
            ),
            "deployment-approved": (
                "Deployment approval quorum has not been met.",
                "Obtain required production approvals.",
            ),
            "rollback-ready": (
                "Rollback readiness has not been established.",
                "Validate the rollback plan and target artifact.",
            ),
            "observability-ready": (
                "Production observability readiness has not passed.",
                "Validate monitoring, alerts, SLOs, and dashboards.",
            ),
        }

        for key, passed in checks.items():
            if not passed:
                summary, recommendation = messages[key]
                findings.append(
                    GovernanceFinding(
                        finding_id=f"production-{key}",
                        category="PRODUCTION_GOVERNANCE",
                        severity="CRITICAL",
                        status="OPEN",
                        summary=summary,
                        recommendation=recommendation,
                    )
                )

        return all(checks.values()), tuple(findings)
