from __future__ import annotations
from pathlib import Path
import tempfile

from trading_ai.deployment.deployment_adapter import InMemoryDeploymentAdapter, DeploymentTargetState
from trading_ai.deployment.deployment_automation_policy import DeploymentAutomationPolicy
from trading_ai.deployment.deployment_automation_profile import DeploymentStrategy, HealthGateResult
from trading_ai.deployment.deployment_audit_service import DeploymentAuditService
from trading_ai.deployment.deployment_health_gate import DeploymentHealthGate
from trading_ai.deployment.deployment_orchestrator import DeploymentOrchestrator
from trading_ai.deployment.deployment_automation_report import DeploymentAutomationReportBuilder
from trading_ai.deployment.release_contract import ReleaseContract

def release(version="2.0.0"):
    from datetime import datetime, timezone
    return ReleaseContract(
        release_id=f"release-{version}",
        version=version,
        git_commit="abc",
        build_timestamp=datetime.now(timezone.utc).isoformat(),
        artifact_checksum="a"*64,
        artifact_location="artifact.tar.gz",
        migration_version="m2",
        configuration_version="c2",
        deployment_targets=("STAGING","PRODUCTION"),
        release_tag=f"v{version}",
        artifact_signed=True,
    )

def main():
    adapter = InMemoryDeploymentAdapter()
    adapter.seed(DeploymentTargetState(
        environment="STAGING", active_slot="blue", candidate_slot=None,
        traffic_percent=100, active_version="1.0.0", candidate_version=None
    ))
    with tempfile.TemporaryDirectory() as temp:
        audit = DeploymentAuditService(Path(temp) / "audit.json")
        orchestrator = DeploymentOrchestrator(adapter=adapter, audit=audit)
        result = orchestrator.deploy(
            deployment_id="dep-bg", release=release(),
            environment="STAGING", strategy=DeploymentStrategy.BLUE_GREEN,
            operator="tester",
        )
        assert result.status == "COMPLETED"
        assert result.active_slot == "green"
        assert result.traffic_percent == 100
        assert len(result.stages) == 3
        assert len(audit.events("dep-bg")) == 2

        report = DeploymentAutomationReportBuilder()
        assert report.write_html(Path(temp) / "report.html", result).exists()
        assert report.write_json(Path(temp) / "report.json", result).exists()

    canary_adapter = InMemoryDeploymentAdapter()
    canary_adapter.seed(DeploymentTargetState(
        environment="PRODUCTION", active_slot="blue", candidate_slot=None,
        traffic_percent=100, active_version="1.0.0", candidate_version=None
    ))
    policy = DeploymentAutomationPolicy(
        canary_initial_traffic_percent=10,
        canary_increment_percent=30,
        canary_max_traffic_percent=100,
        canary_observation_seconds=0,
    )
    canary = DeploymentOrchestrator(
        adapter=canary_adapter, policy=policy
    ).deploy(
        deployment_id="dep-canary", release=release(),
        environment="PRODUCTION", strategy="CANARY",
        operator="tester",
    )
    assert canary.status == "COMPLETED"
    assert canary.traffic_percent == 100
    assert len(canary.stages) == 4

    failing_adapter = InMemoryDeploymentAdapter()
    failing_adapter.seed(DeploymentTargetState(
        environment="STAGING", active_slot="blue", candidate_slot=None,
        traffic_percent=100, active_version="1.0.0", candidate_version=None
    ))
    gate = DeploymentHealthGate(
        lambda environment, slot: HealthGateResult(
            healthy=False, score=0.25, reason="ERROR_RATE_HIGH",
            metrics={"error_rate": 0.75}
        )
    )
    failed = DeploymentOrchestrator(
        adapter=failing_adapter, health_gate=gate
    ).deploy(
        deployment_id="dep-fail", release=release(),
        environment="STAGING", strategy="BLUE_GREEN",
        operator="tester",
    )
    assert failed.status == "ROLLED_BACK"
    assert failed.rollback_executed
    assert failed.active_slot == "blue"

    print(
        "All deployment automation, blue-green, canary, health-gate, "
        "rollback-execution, audit, and reporting assertions passed."
    )

if __name__ == "__main__":
    main()
