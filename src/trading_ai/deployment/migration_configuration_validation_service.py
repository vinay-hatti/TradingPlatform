from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .release_contract import ReleaseContract
from .release_validation_profile import ValidationCheckResult, ValidationFinding


@dataclass(frozen=True)
class MigrationValidationInput:
    current_version: str
    target_version: str
    forward_validated: bool
    rollback_validated: bool
    destructive_operations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfigurationValidationInput:
    version: str
    schema_valid: bool
    secret_references_valid: bool
    environment_overrides_valid: bool = True


class MigrationConfigurationValidationService:
    def validate_migration(
        self,
        release: ReleaseContract,
        value: MigrationValidationInput,
        *,
        require_forward: bool = True,
        require_rollback: bool = True,
    ) -> ValidationCheckResult:
        started = perf_counter()
        findings: list[ValidationFinding] = []
        if value.target_version != release.migration_version:
            findings.append(ValidationFinding(
                check_id='migration.target', category='MIGRATION',
                severity='CRITICAL', status='FAILED',
                summary='Migration target does not match the release contract.',
            ))
        if require_forward and not value.forward_validated:
            findings.append(ValidationFinding(
                check_id='migration.forward', category='MIGRATION',
                severity='CRITICAL', status='FAILED',
                summary='Forward migration validation has not passed.',
            ))
        if require_rollback and not value.rollback_validated:
            findings.append(ValidationFinding(
                check_id='migration.rollback', category='MIGRATION',
                severity='CRITICAL', status='FAILED',
                summary='Rollback migration validation has not passed.',
            ))
        if value.destructive_operations:
            findings.append(ValidationFinding(
                check_id='migration.destructive', category='MIGRATION',
                severity='WARNING', status='REVIEW',
                summary='Migration contains destructive operations.',
                details={'operations': list(value.destructive_operations)},
                remediation='Require explicit data-protection approval.',
            ))
        critical = sum(x.severity == 'CRITICAL' for x in findings)
        return ValidationCheckResult(
            check_id='migration-validation', category='MIGRATION',
            passed=not findings, score=max(0.0, 1.0 - critical * 0.5 - (len(findings)-critical)*0.1),
            findings=tuple(findings), evidence=value.__dict__,
            duration_ms=(perf_counter() - started) * 1000,
        )

    def validate_configuration(
        self,
        release: ReleaseContract,
        value: ConfigurationValidationInput,
        *,
        require_schema: bool = True,
        require_secret_references: bool = True,
    ) -> ValidationCheckResult:
        started = perf_counter()
        findings: list[ValidationFinding] = []
        if value.version != release.configuration_version:
            findings.append(ValidationFinding(
                check_id='configuration.version', category='CONFIGURATION',
                severity='CRITICAL', status='FAILED',
                summary='Configuration version does not match the release contract.',
            ))
        if require_schema and not value.schema_valid:
            findings.append(ValidationFinding(
                check_id='configuration.schema', category='CONFIGURATION',
                severity='CRITICAL', status='FAILED',
                summary='Configuration schema validation failed.',
            ))
        if require_secret_references and not value.secret_references_valid:
            findings.append(ValidationFinding(
                check_id='configuration.secrets', category='CONFIGURATION',
                severity='CRITICAL', status='FAILED',
                summary='One or more secret references are unresolved.',
            ))
        if not value.environment_overrides_valid:
            findings.append(ValidationFinding(
                check_id='configuration.environment', category='CONFIGURATION',
                severity='WARNING', status='FAILED',
                summary='Environment overrides are inconsistent.',
            ))
        critical = sum(x.severity == 'CRITICAL' for x in findings)
        return ValidationCheckResult(
            check_id='configuration-validation', category='CONFIGURATION',
            passed=not findings, score=max(0.0, 1.0 - critical * 0.5 - (len(findings)-critical)*0.1),
            findings=tuple(findings), evidence=value.__dict__,
            duration_ms=(perf_counter() - started) * 1000,
        )
