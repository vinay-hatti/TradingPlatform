from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .release_validation_profile import ValidationCheckResult, ValidationFinding


@dataclass(frozen=True)
class DependencyRequirement:
    name: str
    required_version: str
    installed_version: str | None
    locked: bool = True
    vulnerable: bool = False
    optional: bool = False


class DependencyVerificationService:
    def verify(
        self,
        dependencies: tuple[DependencyRequirement, ...],
        *,
        require_lock: bool = True,
        require_zero_vulnerable: bool = False,
    ) -> ValidationCheckResult:
        started = perf_counter()
        findings: list[ValidationFinding] = []
        for item in dependencies:
            if item.installed_version is None and not item.optional:
                findings.append(ValidationFinding(
                    check_id=f'dependency.{item.name}.installed',
                    category='DEPENDENCY', severity='CRITICAL', status='FAILED',
                    summary=f'Required dependency {item.name} is not installed.',
                    remediation='Install the locked dependency version.',
                ))
                continue
            if (
                item.installed_version is not None
                and item.installed_version != item.required_version
            ):
                findings.append(ValidationFinding(
                    check_id=f'dependency.{item.name}.version',
                    category='DEPENDENCY', severity='CRITICAL', status='FAILED',
                    summary=f'Dependency {item.name} version mismatch.',
                    details={
                        'required': item.required_version,
                        'installed': item.installed_version,
                    },
                    remediation='Synchronize the runtime from the approved lock file.',
                ))
            if require_lock and not item.locked:
                findings.append(ValidationFinding(
                    check_id=f'dependency.{item.name}.lock',
                    category='DEPENDENCY', severity='WARNING', status='FAILED',
                    summary=f'Dependency {item.name} is not lock-governed.',
                    remediation='Add the dependency to the immutable dependency lock.',
                ))
            if require_zero_vulnerable and item.vulnerable:
                findings.append(ValidationFinding(
                    check_id=f'dependency.{item.name}.vulnerability',
                    category='DEPENDENCY', severity='CRITICAL', status='FAILED',
                    summary=f'Dependency {item.name} has a blocking vulnerability.',
                    remediation='Upgrade, patch, or formally waive the vulnerability.',
                ))
        critical = sum(x.severity == 'CRITICAL' for x in findings)
        warnings = sum(x.severity == 'WARNING' for x in findings)
        score = max(0.0, 1.0 - critical * 0.35 - warnings * 0.10)
        return ValidationCheckResult(
            check_id='dependency-verification', category='DEPENDENCY',
            passed=critical == 0 and warnings == 0, score=score,
            findings=tuple(findings),
            evidence={'dependency_count': len(dependencies)},
            duration_ms=(perf_counter() - started) * 1000,
        )
