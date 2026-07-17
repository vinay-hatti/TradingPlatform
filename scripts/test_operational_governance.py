from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from trading_ai.deployment.operational_governance_profile import (
    ComplianceControl,
    ComplianceEvidence,
    DisasterRecoveryPlan,
    OperationalRunbook,
    RunbookStep,
)
from trading_ai.deployment.operational_governance_report import (
    OperationalGovernanceReportBuilder,
)
from trading_ai.deployment.operational_governance_service import (
    OperationalGovernanceService,
)
from trading_ai.deployment.production_governance_service import (
    ProductionChangeRecord,
)


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()

    runbook = OperationalRunbook(
        runbook_id="rb-1",
        name="Production Operations",
        service_name="trading-platform",
        environment="PRODUCTION",
        owner="operations",
        reviewer="engineering-lead",
        version="1.0.0",
        last_reviewed_at=now,
        escalation_path=("on-call", "engineering-lead"),
        prerequisites=("production-access",),
        steps=(
            RunbookStep(
                sequence=1,
                title="Validate health",
                action="Check health and observability.",
                validation="All services healthy.",
                rollback_action="Block release.",
                owner_role="operations",
                estimated_minutes=5,
            ),
        ),
    )

    dr_plan = DisasterRecoveryPlan(
        dr_plan_id="dr-1",
        service_name="trading-platform",
        environment="PRODUCTION",
        owner="operations",
        reviewer="engineering-lead",
        primary_region="primary",
        recovery_region="recovery",
        rto_minutes=30,
        rpo_minutes=5,
        backup_strategy="encrypted-backups",
        restore_procedure="restore database and configuration",
        failover_procedure="promote recovery environment",
        failback_procedure="reconcile and return to primary",
        last_tested_at=now,
        backup_validated=True,
        restore_validated=True,
        test_evidence=("dr-test.json",),
    )

    controls = (
        ComplianceControl(
            control_id="DEPLOY-001",
            framework="INTERNAL",
            title="Deployment approval",
            description="Production deployment approval is required.",
            severity="CRITICAL",
            evidence_types=(
                "approval-record",
                "release-readiness-result",
            ),
        ),
        ComplianceControl(
            control_id="DR-001",
            framework="INTERNAL",
            title="DR validation",
            description="DR testing is required.",
            severity="CRITICAL",
            evidence_types=("dr-test-result",),
        ),
    )

    evidence = (
        ComplianceEvidence(
            control_id="DEPLOY-001",
            evidence_id="e1",
            evidence_type="approval-record",
            location="audit/approval.json",
            collected_at=now,
            collected_by="release-manager",
            valid=True,
        ),
        ComplianceEvidence(
            control_id="DEPLOY-001",
            evidence_id="e2",
            evidence_type="release-readiness-result",
            location="reports/readiness.json",
            collected_at=now,
            collected_by="release-manager",
            valid=True,
        ),
        ComplianceEvidence(
            control_id="DR-001",
            evidence_id="e3",
            evidence_type="dr-test-result",
            location="reports/dr-test.json",
            collected_at=now,
            collected_by="operations",
            valid=True,
        ),
    )

    change = ProductionChangeRecord(
        change_id="chg-1",
        deployment_id="dep-1",
        release_id="release-1",
        environment="PRODUCTION",
        owner="release-manager",
        approver="operations-manager",
        reason="production release",
        risk_level="MEDIUM",
        implementation_window="2026-07-17T12:00:00Z",
        rollback_plan_id="rb-plan-1",
        readiness_result_id="ready-1",
    )

    service = OperationalGovernanceService()
    result = service.evaluate(
        service_name="trading-platform",
        environment="PRODUCTION",
        runbook=runbook,
        dr_plan=dr_plan,
        controls=controls,
        evidence=evidence,
        change_record=change,
        release_ready=True,
        deployment_approved=True,
        rollback_ready=True,
        observability_ready=True,
    )

    assert result.runbook_ready
    assert result.dr_ready
    assert result.compliance_ready
    assert result.production_governance_ready
    assert result.recommendation == "PRODUCTION_GOVERNANCE_READY"
    assert not result.findings

    blocked = service.evaluate(
        service_name="trading-platform",
        environment="PRODUCTION",
        runbook=None,
        dr_plan=None,
        controls=controls,
        evidence=(),
        change_record=None,
        release_ready=False,
        deployment_approved=False,
        rollback_ready=False,
        observability_ready=False,
    )
    assert blocked.recommendation == "BLOCK_PRODUCTION_RELEASE"
    assert blocked.findings
    assert any(
        item.severity == "CRITICAL"
        for item in blocked.findings
    )

    with tempfile.TemporaryDirectory() as temp:
        builder = OperationalGovernanceReportBuilder()
        html_path = builder.write_html(
            Path(temp) / "operational_governance.html",
            result,
        )
        json_path = builder.write_json(
            Path(temp) / "operational_governance.json",
            result,
        )
        assert html_path.exists()
        assert json_path.exists()
        html = html_path.read_text(encoding="utf-8")
        for heading in builder.SECTIONS:
            assert heading in html

    print(
        "All operational runbook, disaster recovery, compliance, "
        "production governance, and reporting assertions passed."
    )


if __name__ == "__main__":
    main()
