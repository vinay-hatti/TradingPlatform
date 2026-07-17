from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class DeploymentAutomationPolicy:
    default_strategy: str = "BLUE_GREEN"
    require_health_gate: bool = True
    minimum_health_score: float = 0.95
    canary_initial_traffic_percent: int = 5
    canary_increment_percent: int = 20
    canary_max_traffic_percent: int = 100
    canary_observation_seconds: float = 60.0
    rollback_on_health_failure: bool = True
    rollback_on_timeout: bool = True
    max_stage_seconds: float = 900.0
    require_audit_events: bool = True

    def validate(self) -> None:
        if self.default_strategy not in {"BLUE_GREEN", "CANARY", "IN_PLACE"}:
            raise ValueError("Unsupported default_strategy")
        if not 0 <= self.minimum_health_score <= 1:
            raise ValueError("minimum_health_score must be between 0 and 1")
        for value in (
            self.canary_initial_traffic_percent,
            self.canary_increment_percent,
            self.canary_max_traffic_percent,
        ):
            if not 0 < value <= 100:
                raise ValueError("Canary traffic percentages must be in (0, 100]")
        if self.canary_initial_traffic_percent > self.canary_max_traffic_percent:
            raise ValueError("Initial canary traffic cannot exceed maximum")
        if self.max_stage_seconds <= 0:
            raise ValueError("max_stage_seconds must be positive")
