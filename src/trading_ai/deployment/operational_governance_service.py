from __future__ import annotations

from .compliance_governance_service import (
    ComplianceGovernanceService,
)
from .disaster_recovery_service import DisasterRecoveryService
from .operational_governance_policy import OperationalGovernancePolicy
from .operational_governance_profile import (
    ComplianceControl,
    ComplianceEvidence,
    DisasterRecoveryPlan,
    OperationalGovernanceResult,
    OperationalRunbook,
)
from .operational_runbook_service import OperationalRunbookService
from .production_governance_service import (
    ProductionChangeRecord,
    ProductionGovernanceService,
)


class OperationalGovernanceService:
    def __init__(
        self,
        policy: OperationalGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalGovernancePolicy()
        self.runbooks = OperationalRunbookService(self.policy)
        self.dr = DisasterRecoveryService(self.policy)
        self.compliance = ComplianceGovernanceService(self.policy)
        self.production = ProductionGovernanceService(self.policy)

    def evaluate(
        self,
        *,
        service_name: str,
        environment: str,
        runbook: OperationalRunbook | None,
        dr_plan: DisasterRecoveryPlan | None,
        controls: tuple[ComplianceControl, ...],
        evidence: tuple[ComplianceEvidence, ...],
        change_record: ProductionChangeRecord | None,
        release_ready: bool,
        deployment_approved: bool,
        rollback_ready: bool,
        observability_ready: bool,
    ) -> OperationalGovernanceResult:
        runbook_ready, runbook_score, runbook_findings = (
            self.runbooks.evaluate(runbook)
        )
        dr_ready, dr_score, dr_findings = self.dr.evaluate(dr_plan)
        compliance_ready, compliance_score, compliance_findings = (
            self.compliance.evaluate(controls, evidence)
        )
        production_ready, production_findings = self.production.evaluate(
            environment=environment,
            change_record=change_record,
            release_ready=release_ready,
            deployment_approved=deployment_approved,
            rollback_ready=rollback_ready,
            observability_ready=observability_ready,
        )

        findings = (
            runbook_findings
            + dr_findings
            + compliance_findings
            + production_findings
        )
        ready = (
            runbook_ready
            and dr_ready
            and compliance_ready
            and production_ready
        )
        return OperationalGovernanceResult(
            service_name=service_name,
            environment=environment,
            runbook_ready=runbook_ready,
            dr_ready=dr_ready,
            compliance_ready=compliance_ready,
            production_governance_ready=production_ready,
            runbook_score=runbook_score,
            dr_score=dr_score,
            compliance_score=compliance_score,
            findings=findings,
            recommendation=(
                "PRODUCTION_GOVERNANCE_READY"
                if ready else "BLOCK_PRODUCTION_RELEASE"
            ),
        )
