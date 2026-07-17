from __future__ import annotations

from .release_validation_policy import ReleaseValidationPolicy
from .release_validation_profile import (
    ReleaseReadinessResult,
    ValidationCheckResult,
)


CATEGORY_WEIGHT_KEYS = {
    'CONTRACT': 'contract',
    'ARTIFACT': 'artifact',
    'DEPENDENCY': 'dependencies',
    'COMPATIBILITY': 'compatibility',
    'MIGRATION': 'migrations',
    'CONFIGURATION': 'configuration',
    'SMOKE_TEST': 'smoke_tests',
}


class ReleaseReadinessEngine:
    def __init__(self, policy: ReleaseValidationPolicy | None = None) -> None:
        self.policy = policy or ReleaseValidationPolicy()
        self.policy.validate()

    def evaluate(
        self,
        *,
        release_id: str,
        version: str,
        environment: str,
        checks: tuple[ValidationCheckResult, ...],
    ) -> ReleaseReadinessResult:
        by_category = {item.category: item for item in checks}
        weighted_score = 0.0
        for category, weight_name in CATEGORY_WEIGHT_KEYS.items():
            weight = getattr(self.policy.weights, weight_name)
            check = by_category.get(category)
            weighted_score += weight * (check.score if check else 0.0)
        findings = tuple(
            finding for check in checks for finding in check.findings
        )
        critical = sum(x.severity == 'CRITICAL' for x in findings)
        warnings = sum(x.severity == 'WARNING' for x in findings)
        threshold = self.policy.threshold_for(environment)
        blocked = self.policy.block_on_critical_finding and critical > 0
        ready = weighted_score >= threshold and not blocked
        if ready:
            recommendation = 'RELEASE_READY'
        elif blocked:
            recommendation = 'BLOCK_CRITICAL_FINDINGS'
        else:
            recommendation = 'IMPROVE_READINESS_SCORE'
        return ReleaseReadinessResult(
            release_id=release_id, version=version,
            environment=environment.upper(), score=round(weighted_score, 6),
            threshold=threshold, ready=ready,
            critical_findings=critical, warning_findings=warnings,
            checks=checks, recommendation=recommendation,
        )
