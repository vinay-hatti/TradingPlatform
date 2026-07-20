from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioComparisonPolicy:
    minimum_scenarios: int = 3
    maximum_scenarios: int = 12
    probability_tolerance: float = 0.001
    low_sensitivity_threshold: float = 0.05
    moderate_sensitivity_threshold: float = 0.15
    high_sensitivity_threshold: float = 0.30
    minimum_confidence_for_buy: float = 0.65
    minimum_confidence_for_strong_buy: float = 0.80
    minimum_score_for_buy: float = 70.0
    minimum_score_for_strong_buy: float = 85.0
    reject_score_threshold: float = 35.0
    negative_expected_value_threshold: float = 0.0
    return_weight: float = 0.35
    volatility_weight: float = 0.15
    drawdown_weight: float = 0.25
    confidence_weight: float = 0.15
    probability_weight: float = 0.10

    def validate(self) -> None:
        if self.minimum_scenarios <= 0:
            raise ValueError("minimum_scenarios must be positive.")
        if self.maximum_scenarios < self.minimum_scenarios:
            raise ValueError(
                "maximum_scenarios cannot be below minimum_scenarios."
            )
        thresholds = (
            self.low_sensitivity_threshold,
            self.moderate_sensitivity_threshold,
            self.high_sensitivity_threshold,
        )
        if not (
            0.0 <= thresholds[0] <= thresholds[1] <= thresholds[2]
        ):
            raise ValueError(
                "Sensitivity thresholds must be non-decreasing."
            )
        total_weight = (
            self.return_weight
            + self.volatility_weight
            + self.drawdown_weight
            + self.confidence_weight
            + self.probability_weight
        )
        if abs(total_weight - 1.0) > 1e-9:
            raise ValueError("Scenario comparison weights must sum to 1.")
