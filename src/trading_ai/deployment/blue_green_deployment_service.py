from __future__ import annotations
from datetime import datetime, timezone
from .deployment_adapter import DeploymentAdapter
from .deployment_automation_policy import DeploymentAutomationPolicy
from .deployment_automation_profile import DeploymentStageResult, HealthGateResult
from .deployment_health_gate import DeploymentHealthGate

class BlueGreenDeploymentService:
    def __init__(self, adapter: DeploymentAdapter, health_gate: DeploymentHealthGate,
                 policy: DeploymentAutomationPolicy | None = None) -> None:
        self.adapter = adapter
        self.health_gate = health_gate
        self.policy = policy or DeploymentAutomationPolicy()
        self.policy.validate()

    def execute(self, *, environment: str, artifact_location: str, version: str):
        state = self.adapter.current_state(environment)
        candidate = "green" if state.active_slot == "blue" else "blue"
        stages = []
        start = datetime.now(timezone.utc).isoformat()
        self.adapter.deploy_to_slot(
            environment=environment, slot=candidate,
            artifact_location=artifact_location, version=version
        )
        stages.append(DeploymentStageResult(
            "DEPLOY_CANDIDATE", "SUCCESS", f"Deployed {version} to {candidate}",
            start, datetime.now(timezone.utc).isoformat(), {"slot": candidate}
        ))
        health = self.health_gate.evaluate(environment, candidate)
        stages.append(DeploymentStageResult(
            "HEALTH_GATE", "SUCCESS" if health.healthy else "FAILED",
            health.reason, start, datetime.now(timezone.utc).isoformat(),
            {"score": health.score, "metrics": health.metrics}
        ))
        if self.policy.require_health_gate and (
            not health.healthy or health.score < self.policy.minimum_health_score
        ):
            self.adapter.remove_slot(environment=environment, slot=candidate)
            return False, state.active_slot, candidate, tuple(stages), health
        self.adapter.set_traffic(environment=environment, slot=candidate, percent=100)
        self.adapter.promote_slot(environment=environment, slot=candidate)
        stages.append(DeploymentStageResult(
            "SWITCH_TRAFFIC", "SUCCESS", "Traffic switched atomically",
            start, datetime.now(timezone.utc).isoformat(), {"slot": candidate, "traffic": 100}
        ))
        return True, candidate, state.active_slot, tuple(stages), health
