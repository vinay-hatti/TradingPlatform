from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRegimeDriftPolicy:
    minimum_reference_observations: int = 20
    minimum_recent_observations: int = 10
    warning_psi: float = 0.10
    severe_psi: float = 0.25
    critical_psi: float = 0.40
    warning_score_shift: float = 10.0
    severe_score_shift: float = 20.0
    warning_transition_rate_shift: float = 0.15
    severe_transition_rate_shift: float = 0.30
    minimum_drift_score: float = 50.0
    reject_critical_drift: bool = True
