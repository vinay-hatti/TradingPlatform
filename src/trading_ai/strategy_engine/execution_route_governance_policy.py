from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionRouteGovernancePolicy:
    """Institutional policy for versioned route registration and promotion."""

    minimum_champion_observations: int = 100
    minimum_challenger_observations: int = 50
    minimum_governance_score: float = 70.0
    minimum_route_score: float = 60.0
    minimum_confidence_score: float = 55.0
    minimum_score_improvement: float = 2.0
    minimum_shortfall_improvement_bps: float = 0.0
    maximum_fill_ratio_deterioration: float = 0.02
    maximum_latency_deterioration_seconds: float = 2.0
    maximum_spread_deterioration_bps: float = 2.0
    require_governance_approval: bool = True
    require_challenger_allowed: bool = True
    reject_severe_governance_drift: bool = True
    allow_initial_activation: bool = True
    preserve_previous_champion: bool = True
