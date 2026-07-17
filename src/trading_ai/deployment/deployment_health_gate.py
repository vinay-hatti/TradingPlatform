from __future__ import annotations
from collections.abc import Callable
from .deployment_automation_profile import HealthGateResult

class DeploymentHealthGate:
    def __init__(self, evaluator: Callable[[str, str], HealthGateResult] | None = None) -> None:
        self.evaluator = evaluator or self._default

    @staticmethod
    def _default(environment: str, slot: str) -> HealthGateResult:
        return HealthGateResult(
            healthy=True, score=1.0, reason="DEFAULT_HEALTHY",
            metrics={"availability": 1.0, "error_rate": 0.0}
        )

    def evaluate(self, environment: str, slot: str) -> HealthGateResult:
        return self.evaluator(environment, slot)
