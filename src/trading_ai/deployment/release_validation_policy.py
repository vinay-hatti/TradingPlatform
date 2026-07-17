from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReadinessWeights:
    contract: float = 0.20
    artifact: float = 0.20
    dependencies: float = 0.20
    compatibility: float = 0.15
    migrations: float = 0.10
    configuration: float = 0.05
    smoke_tests: float = 0.10

    def validate(self) -> None:
        values = tuple(self.__dict__.values())
        if any(value < 0 for value in values):
            raise ValueError('Readiness weights cannot be negative')
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError('Readiness weights must sum to 1.0')


@dataclass(frozen=True)
class ReleaseValidationPolicy:
    minimum_readiness_score: float = 0.90
    production_minimum_readiness_score: float = 0.97
    block_on_critical_finding: bool = True
    require_artifact_exists: bool = True
    require_checksum_match: bool = True
    require_signature_verification: bool = True
    require_dependency_lock: bool = True
    require_zero_vulnerable_dependencies: bool = False
    require_database_compatibility: bool = True
    require_schema_compatibility: bool = True
    require_migration_forward_validation: bool = True
    require_migration_rollback_validation: bool = True
    require_configuration_schema_validation: bool = True
    require_secret_reference_validation: bool = True
    require_smoke_tests: bool = True
    smoke_test_timeout_seconds: float = 120.0
    weights: ReadinessWeights = field(default_factory=ReadinessWeights)

    def validate(self) -> None:
        if not 0 <= self.minimum_readiness_score <= 1:
            raise ValueError('minimum_readiness_score must be between 0 and 1')
        if not 0 <= self.production_minimum_readiness_score <= 1:
            raise ValueError(
                'production_minimum_readiness_score must be between 0 and 1'
            )
        if self.production_minimum_readiness_score < self.minimum_readiness_score:
            raise ValueError(
                'production readiness cannot be lower than general readiness'
            )
        if self.smoke_test_timeout_seconds <= 0:
            raise ValueError('smoke_test_timeout_seconds must be positive')
        self.weights.validate()

    def threshold_for(self, environment: str) -> float:
        if environment.upper() == 'PRODUCTION':
            return self.production_minimum_readiness_score
        return self.minimum_readiness_score
