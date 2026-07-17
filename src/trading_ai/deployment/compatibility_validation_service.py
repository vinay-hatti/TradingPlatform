from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .release_contract import ReleaseContract
from .release_validation_profile import ValidationCheckResult, ValidationFinding


@dataclass(frozen=True)
class RuntimeCompatibilityProfile:
    platform_version: str
    database_version: str
    schema_version: str
    python_version: str = ''
    operating_system: str = ''


def _version_tuple(value: str) -> tuple[int, ...]:
    core = value.split('-', 1)[0].split('+', 1)[0]
    return tuple(int(part) for part in core.split('.') if part.isdigit())


class CompatibilityValidationService:
    def validate(
        self,
        release: ReleaseContract,
        runtime: RuntimeCompatibilityProfile,
    ) -> ValidationCheckResult:
        started = perf_counter()
        findings: list[ValidationFinding] = []
        if (
            release.supported_database_versions
            and runtime.database_version not in release.supported_database_versions
        ):
            findings.append(ValidationFinding(
                check_id='compatibility.database', category='COMPATIBILITY',
                severity='CRITICAL', status='FAILED',
                summary='Database version is unsupported by this release.',
                details={'runtime': runtime.database_version},
            ))
        if (
            release.supported_schema_versions
            and runtime.schema_version not in release.supported_schema_versions
        ):
            findings.append(ValidationFinding(
                check_id='compatibility.schema', category='COMPATIBILITY',
                severity='CRITICAL', status='FAILED',
                summary='Schema version is unsupported by this release.',
                details={'runtime': runtime.schema_version},
            ))
        platform = _version_tuple(runtime.platform_version)
        if release.minimum_platform_version and platform < _version_tuple(release.minimum_platform_version):
            findings.append(ValidationFinding(
                check_id='compatibility.platform.minimum',
                category='COMPATIBILITY', severity='CRITICAL', status='FAILED',
                summary='Runtime platform version is below the release minimum.',
            ))
        if release.maximum_platform_version and platform > _version_tuple(release.maximum_platform_version):
            findings.append(ValidationFinding(
                check_id='compatibility.platform.maximum',
                category='COMPATIBILITY', severity='CRITICAL', status='FAILED',
                summary='Runtime platform version exceeds the release maximum.',
            ))
        return ValidationCheckResult(
            check_id='runtime-compatibility', category='COMPATIBILITY',
            passed=not findings,
            score=1.0 if not findings else max(0.0, 1.0 - 0.5 * len(findings)),
            findings=tuple(findings), evidence=runtime.__dict__,
            duration_ms=(perf_counter() - started) * 1000,
        )
