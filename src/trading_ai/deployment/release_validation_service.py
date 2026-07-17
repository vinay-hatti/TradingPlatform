from __future__ import annotations

from time import perf_counter

from .artifact_validation_service import ArtifactValidationService
from .compatibility_validation_service import (
    CompatibilityValidationService,
    RuntimeCompatibilityProfile,
)
from .dependency_verification_service import (
    DependencyRequirement,
    DependencyVerificationService,
)
from .migration_configuration_validation_service import (
    ConfigurationValidationInput,
    MigrationConfigurationValidationService,
    MigrationValidationInput,
)
from .release_contract import ReleaseContract
from .release_readiness_engine import ReleaseReadinessEngine
from .release_validation_policy import ReleaseValidationPolicy
from .release_validation_profile import ValidationCheckResult, ValidationFinding
from .smoke_test_service import SmokeTestDefinition, SmokeTestService


class ReleaseValidationService:
    def __init__(self, policy: ReleaseValidationPolicy | None = None) -> None:
        self.policy = policy or ReleaseValidationPolicy()
        self.policy.validate()
        self.artifact = ArtifactValidationService()
        self.dependencies = DependencyVerificationService()
        self.compatibility = CompatibilityValidationService()
        self.migration_configuration = MigrationConfigurationValidationService()
        self.smoke_tests = SmokeTestService()
        self.readiness = ReleaseReadinessEngine(self.policy)

    def validate(
        self,
        *,
        release: ReleaseContract,
        environment: str,
        artifact_path=None,
        signature_verified=None,
        dependencies: tuple[DependencyRequirement, ...] = (),
        runtime: RuntimeCompatibilityProfile,
        migration: MigrationValidationInput,
        configuration: ConfigurationValidationInput,
        smoke_tests: tuple[SmokeTestDefinition, ...] = (),
        smoke_test_cwd: str | None = None,
        smoke_test_environment: dict[str, str] | None = None,
    ):
        started = perf_counter()
        contract_valid, contract_errors = release.validate()
        contract_findings = tuple(
            ValidationFinding(
                check_id=f'contract.{error.lower()}', category='CONTRACT',
                severity='CRITICAL', status='FAILED', summary=error,
            ) for error in contract_errors
        )
        contract_check = ValidationCheckResult(
            check_id='release-contract', category='CONTRACT',
            passed=contract_valid, score=1.0 if contract_valid else 0.0,
            findings=contract_findings,
            evidence={'release_id': release.release_id, 'version': release.version},
        )
        artifact_check = self.artifact.validate(
            release, artifact_path=artifact_path,
            signature_verified=signature_verified,
            require_exists=self.policy.require_artifact_exists,
            require_checksum=self.policy.require_checksum_match,
            require_signature=self.policy.require_signature_verification,
        )
        dependency_check = self.dependencies.verify(
            dependencies,
            require_lock=self.policy.require_dependency_lock,
            require_zero_vulnerable=self.policy.require_zero_vulnerable_dependencies,
        )
        compatibility_check = self.compatibility.validate(release, runtime)
        migration_check = self.migration_configuration.validate_migration(
            release, migration,
            require_forward=self.policy.require_migration_forward_validation,
            require_rollback=self.policy.require_migration_rollback_validation,
        )
        configuration_check = self.migration_configuration.validate_configuration(
            release, configuration,
            require_schema=self.policy.require_configuration_schema_validation,
            require_secret_references=self.policy.require_secret_reference_validation,
        )
        _, smoke_check = self.smoke_tests.execute(
            smoke_tests,
            default_timeout_seconds=self.policy.smoke_test_timeout_seconds,
            cwd=smoke_test_cwd,
            base_environment=smoke_test_environment,
        )
        if self.policy.require_smoke_tests and not smoke_tests:
            missing = ValidationFinding(
                check_id='smoke.required', category='SMOKE_TEST',
                severity='CRITICAL', status='FAILED',
                summary='No required smoke tests were supplied.',
            )
            smoke_check = ValidationCheckResult(
                check_id='smoke-test-validation', category='SMOKE_TEST',
                passed=False, score=0.0, findings=(missing,), evidence={'test_count': 0}
            )
        checks = (
            contract_check, artifact_check, dependency_check,
            compatibility_check, migration_check,
            configuration_check, smoke_check,
        )
        result = self.readiness.evaluate(
            release_id=release.release_id, version=release.version,
            environment=environment, checks=checks,
        )
        return result
