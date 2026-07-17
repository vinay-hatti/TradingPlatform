from __future__ import annotations
from datetime import datetime, timezone
from .blue_green_deployment_service import BlueGreenDeploymentService
from .canary_deployment_service import CanaryDeploymentService
from .deployment_adapter import DeploymentAdapter
from .deployment_automation_policy import DeploymentAutomationPolicy
from .deployment_automation_profile import DeploymentAutomationResult, DeploymentStrategy
from .deployment_audit_service import DeploymentAuditEvent, DeploymentAuditService
from .deployment_health_gate import DeploymentHealthGate
from .release_contract import ReleaseContract
from .rollback_execution_service import RollbackExecutionService
from .rollback_policy import RollbackPlan, RollbackTrigger

class DeploymentOrchestrator:
    def __init__(self, *, adapter: DeploymentAdapter,
                 policy: DeploymentAutomationPolicy | None = None,
                 health_gate: DeploymentHealthGate | None = None,
                 audit: DeploymentAuditService | None = None) -> None:
        self.adapter = adapter
        self.policy = policy or DeploymentAutomationPolicy()
        self.policy.validate()
        self.health_gate = health_gate or DeploymentHealthGate()
        self.audit = audit or DeploymentAuditService()
        self.blue_green = BlueGreenDeploymentService(adapter, self.health_gate, self.policy)
        self.canary = CanaryDeploymentService(adapter, self.health_gate, self.policy)
        self.rollback = RollbackExecutionService(adapter)

    def deploy(self, *, deployment_id: str, release: ReleaseContract,
               environment: str, strategy: DeploymentStrategy | str,
               operator: str) -> DeploymentAutomationResult:
        started = datetime.now(timezone.utc).isoformat()
        strategy = DeploymentStrategy(strategy)
        original = self.adapter.current_state(environment)
        self.audit.record(DeploymentAuditEvent(
            deployment_id=deployment_id, event_type="AUTOMATION_STARTED",
            environment=environment, release_version=release.version,
            operator=operator, status="STARTED", details={"strategy": strategy.value}
        ))
        rollback_executed = False
        if strategy == DeploymentStrategy.BLUE_GREEN:
            ok, active, candidate, stages, health = self.blue_green.execute(
                environment=environment,
                artifact_location=release.artifact_location,
                version=release.version,
            )
            traffic = 100 if ok else 0
        elif strategy == DeploymentStrategy.CANARY:
            ok, active, candidate, traffic, stages, health = self.canary.execute(
                environment=environment,
                artifact_location=release.artifact_location,
                version=release.version,
            )
        else:
            candidate = original.active_slot
            self.adapter.deploy_to_slot(
                environment=environment, slot=candidate,
                artifact_location=release.artifact_location,
                version=release.version
            )
            health = self.health_gate.evaluate(environment, candidate)
            ok = health.healthy and health.score >= self.policy.minimum_health_score
            stages = ()
            active = candidate if ok else original.active_slot
            traffic = 100 if ok else 0

        status = "COMPLETED" if ok else "FAILED"
        recommendation = "DEPLOYMENT_COMPLETED" if ok else "ROLLBACK_REQUIRED"

        if not ok and self.policy.rollback_on_health_failure and original.active_version:
            plan = RollbackPlan(
                deployment_id=deployment_id,
                trigger=RollbackTrigger.HEALTH_DEGRADATION,
                target_artifact_version=original.active_version,
                target_artifact_checksum="0" * 64,
                schema_rollback_version="previous",
                configuration_rollback_version="previous",
                operator=operator,
            )
            rb = self.rollback.execute(
                environment=environment, plan=plan,
                restore_slot=original.active_slot
            )
            rollback_executed = rb.success
            status = "ROLLED_BACK" if rb.success else "FAILED"
            recommendation = rb.reason

        completed = datetime.now(timezone.utc).isoformat()
        self.audit.record(DeploymentAuditEvent(
            deployment_id=deployment_id, event_type="AUTOMATION_COMPLETED",
            environment=environment, release_version=release.version,
            operator=operator, status=status,
            details={
                "strategy": strategy.value,
                "health_score": health.score,
                "rollback_executed": rollback_executed,
            }
        ))
        return DeploymentAutomationResult(
            deployment_id=deployment_id, release_id=release.release_id,
            environment=environment, strategy=strategy.value,
            status=status, active_slot=active, candidate_slot=candidate,
            traffic_percent=traffic, rollback_executed=rollback_executed,
            stages=tuple(stages), recommendation=recommendation,
            started_at=started, completed_at=completed,
        )
