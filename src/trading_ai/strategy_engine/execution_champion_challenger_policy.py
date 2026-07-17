from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionChampionChallengerPolicy:
    """Institutional policy for champion-challenger route governance."""

    minimum_champion_observations: int = 100
    minimum_challenger_observations: int = 75
    minimum_evaluation_score: float = 65.0
    minimum_confidence_score: float = 60.0
    minimum_route_score_improvement: float = 2.0
    minimum_shortfall_improvement_bps: float = 0.0
    minimum_governance_score: float = 70.0
    maximum_fill_ratio_deterioration: float = 0.02
    maximum_latency_deterioration_seconds: float = 2.0
    maximum_spread_deterioration_bps: float = 2.0
    maximum_market_impact_deterioration_bps: float = 1.5
    maximum_effective_spread_deterioration_bps: float = 1.5
    require_same_route_type: bool = True
    require_governance_approval: bool = True
    reject_severe_drift: bool = True
    auto_promote: bool = False
    preserve_champion_on_rejection: bool = True
