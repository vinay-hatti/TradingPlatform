from __future__ import annotations

from .final_readiness_policy import FinalReadinessPolicy
from .final_readiness_profile import (
    BenchmarkResult,
    FinalReadinessResult,
    RegressionResult,
    ReleaseSignOff,
    ValidationCheck,
)


class FinalReadinessEngine:
    WEIGHTS = {
        "REGRESSION": 0.30,
        "PERFORMANCE": 0.20,
        "DEPLOYMENT": 0.15,
        "OPERATIONAL_GOVERNANCE": 0.15,
        "OBSERVABILITY": 0.10,
        "DOCUMENTATION": 0.10,
    }

    def __init__(
        self,
        policy: FinalReadinessPolicy | None = None,
    ) -> None:
        self.policy = policy or FinalReadinessPolicy()
        self.policy.validate()

    def evaluate(
        self,
        *,
        project_name: str,
        milestone: str,
        phase: str,
        checks: tuple[ValidationCheck, ...],
        benchmarks: tuple[BenchmarkResult, ...],
        regressions: tuple[RegressionResult, ...],
        documentation_score: float,
        sign_off: ReleaseSignOff | None,
    ) -> FinalReadinessResult:
        category_scores: dict[str, list[float]] = {}

        for check in checks:
            category_scores.setdefault(
                check.category.upper(), []
            ).append(check.score)

        regression_pass_rate = (
            sum(item.pass_rate for item in regressions)
            / len(regressions)
            if regressions else 0.0
        )
        benchmark_pass_rate = (
            sum(1.0 if item.passed else 0.0 for item in benchmarks)
            / len(benchmarks)
            if benchmarks else 0.0
        )

        category_scores.setdefault("REGRESSION", []).append(
            regression_pass_rate
        )
        category_scores.setdefault("PERFORMANCE", []).append(
            benchmark_pass_rate
        )
        category_scores.setdefault("DOCUMENTATION", []).append(
            documentation_score
        )

        weighted_score = 0.0
        total_weight = 0.0
        for category, weight in self.WEIGHTS.items():
            values = category_scores.get(category, ())
            score = sum(values) / len(values) if values else 0.0
            weighted_score += score * weight
            total_weight += weight

        overall_score = (
            weighted_score / total_weight
            if total_weight else 0.0
        )

        critical = sum(
            check.required and not check.passed
            and check.evidence.get("severity", "").upper() == "CRITICAL"
            for check in checks
        )
        high = sum(
            check.required and not check.passed
            and check.evidence.get("severity", "").upper() == "HIGH"
            for check in checks
        )

        required_checks_pass = all(
            (not check.required) or check.passed
            for check in checks
        )
        regressions_pass = (
            regression_pass_rate
            >= self.policy.minimum_regression_pass_rate
        )
        benchmarks_pass = (
            benchmark_pass_rate
            >= self.policy.minimum_benchmark_pass_rate
        )
        documentation_pass = (
            documentation_score
            >= self.policy.minimum_release_documentation_score
        )
        sign_off_pass = (
            sign_off is not None
            and sign_off.final_decision == "APPROVED"
        )

        ready = (
            overall_score >= self.policy.minimum_overall_score
            and required_checks_pass
            and regressions_pass
            and benchmarks_pass
            and documentation_pass
            and critical <= self.policy.maximum_critical_findings
            and high <= self.policy.maximum_high_findings
            and sign_off_pass
        )

        return FinalReadinessResult(
            project_name=project_name,
            milestone=milestone,
            phase=phase,
            overall_score=overall_score,
            ready_for_production=ready,
            critical_findings=critical,
            high_findings=high,
            regression_pass_rate=regression_pass_rate,
            benchmark_pass_rate=benchmark_pass_rate,
            documentation_score=documentation_score,
            checks=checks,
            benchmarks=benchmarks,
            regressions=regressions,
            sign_off=sign_off,
            recommendation=(
                "PROJECT_PRODUCTION_READY"
                if ready else "BLOCK_FINAL_PRODUCTION_RELEASE"
            ),
        )
