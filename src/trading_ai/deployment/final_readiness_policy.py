from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinalReadinessPolicy:
    minimum_overall_score: float = 0.98
    require_all_critical_gates: bool = True
    require_end_to_end_regression: bool = True
    require_performance_benchmark: bool = True
    require_operational_governance: bool = True
    require_observability_readiness: bool = True
    require_deployment_rollback_validation: bool = True
    maximum_critical_findings: int = 0
    maximum_high_findings: int = 0
    minimum_regression_pass_rate: float = 1.0
    minimum_benchmark_pass_rate: float = 1.0
    minimum_release_documentation_score: float = 1.0

    def validate(self) -> None:
        for name, value in (
            ("minimum_overall_score", self.minimum_overall_score),
            ("minimum_regression_pass_rate", self.minimum_regression_pass_rate),
            ("minimum_benchmark_pass_rate", self.minimum_benchmark_pass_rate),
            (
                "minimum_release_documentation_score",
                self.minimum_release_documentation_score,
            ),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.maximum_critical_findings < 0:
            raise ValueError("maximum_critical_findings cannot be negative")
        if self.maximum_high_findings < 0:
            raise ValueError("maximum_high_findings cannot be negative")
