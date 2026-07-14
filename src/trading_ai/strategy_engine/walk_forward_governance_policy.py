from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardGovernancePolicy:
    minimum_completed_windows: int = 3
    minimum_challenger_score: float = 55.0
    minimum_score_improvement: float = 2.0
    minimum_oos_return_improvement: float = 0.0
    minimum_sharpe_improvement: float = 0.0
    maximum_drawdown_deterioration_pct: float = 0.03
    maximum_degradation_deterioration_pct: float = 0.05
    minimum_parameter_stability: float = 45.0
    reject_critical_severity: bool = True
    automatic_promotion_enabled: bool = False
