from __future__ import annotations
from datetime import datetime, timezone
from .deployment_adapter import DeploymentAdapter
from .deployment_automation_policy import DeploymentAutomationPolicy
from .deployment_automation_profile import DeploymentStageResult
from .deployment_health_gate import DeploymentHealthGate

class CanaryDeploymentService:
    def __init__(self, adapter: DeploymentAdapter, health_gate: DeploymentHealthGate,
                 policy: DeploymentAutomationPolicy | None = None) -> None:
        self.adapter = adapter
        self.health_gate = health_gate
        self.policy = policy or DeploymentAutomationPolicy()
        self.policy.validate()

    def execute(self, *, environment: str, artifact_location: str, version: str):
        state = self.adapter.current_state(environment)
        candidate = f"canary-{version}"
        stages = []
        started = datetime.now(timezone.utc).isoformat()
        self.adapter.deploy_to_slot(
            environment=environment, slot=candidate,
            artifact_location=artifact_location, version=version
        )
        traffic = self.policy.canary_initial_traffic_percent
        last_health = None
        while traffic <= self.policy.canary_max_traffic_percent:
            self.adapter.set_traffic(environment=environment, slot=candidate, percent=traffic)
            health = self.health_gate.evaluate(environment, candidate)
            last_health = health
            stages.append(DeploymentStageResult(
                f"CANARY_{traffic}", "SUCCESS" if health.healthy else "FAILED",
                health.reason, started, datetime.now(timezone.utc).isoformat(),
                {"traffic_percent": traffic, "score": health.score, "metrics": health.metrics}
            ))
            if not health.healthy or health.score < self.policy.minimum_health_score:
                self.adapter.remove_slot(environment=environment, slot=candidate)
                return False, state.active_slot, candidate, traffic, tuple(stages), health
            if traffic == self.policy.canary_max_traffic_percent:
                break
            traffic = min(
                self.policy.canary_max_traffic_percent,
                traffic + self.policy.canary_increment_percent,
            )
        self.adapter.promote_slot(environment=environment, slot=candidate)
        return True, candidate, state.active_slot, 100, tuple(stages), last_health
