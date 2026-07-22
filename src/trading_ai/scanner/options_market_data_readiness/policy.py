from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionDataReadinessPolicy:
    coverage_weight: float = 0.50
    quality_weight: float = 0.50

    ready_score: float = 0.75
    review_score: float = 0.45

    fail_if_coverage_failed: bool = True
    fail_if_quality_failed: bool = True

    require_minimum_contracts_for_ready: int = 10
    require_minimum_expirations_for_ready: int = 1

    @staticmethod
    def clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def validate(self) -> None:
        total = self.coverage_weight + self.quality_weight
        if total <= 0:
            raise ValueError("readiness weights must sum to a positive value")
        if not 0 <= self.review_score <= self.ready_score <= 1:
            raise ValueError(
                "expected 0 <= review_score <= ready_score <= 1"
            )
