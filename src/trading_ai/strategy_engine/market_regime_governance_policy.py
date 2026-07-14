from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRegimeGovernancePolicy:
    minimum_evaluation_observations: int = 100
    minimum_accuracy_improvement: float = 0.01
    minimum_forecast_accuracy_improvement: float = 0.005
    minimum_transition_f1_improvement: float = 0.0
    maximum_critical_false_positive_deterioration: float = 0.01
    minimum_challenger_score: float = 60.0
    reject_critical_drift: bool = True
    automatic_promotion_enabled: bool = False
