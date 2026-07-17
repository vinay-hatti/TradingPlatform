from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartupReadinessPolicy:
    """Aggregate startup policy across runtime, environment, and secrets."""

    minimum_readiness_score: float = 90.0
    require_runtime_safety: bool = True
    require_environment_registry: bool = True
    require_active_environment_version: bool = True
    require_secret_governance: bool = True
    require_configuration_fingerprint_match: bool = True
    fail_closed: bool = True
    production_environment: str = "production"
    runtime_weight: float = 0.40
    environment_weight: float = 0.25
    secret_weight: float = 0.35

    def validate(self) -> None:
        if not 0.0 <= self.minimum_readiness_score <= 100.0:
            raise ValueError("minimum_readiness_score must be between 0 and 100")
        weights = (self.runtime_weight, self.environment_weight, self.secret_weight)
        if any(value < 0.0 for value in weights):
            raise ValueError("startup readiness weights cannot be negative")
        if sum(weights) <= 0.0:
            raise ValueError("at least one startup readiness weight must be positive")

    def normalized_weights(self) -> tuple[float, float, float]:
        total = self.runtime_weight + self.environment_weight + self.secret_weight
        return (
            self.runtime_weight / total,
            self.environment_weight / total,
            self.secret_weight / total,
        )
