from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyScorePolicy:
    """
    Institutional acceptance and penalty policy.
    """

    minimum_composite_score: float = 65.0
    preferred_composite_score: float = 75.0
    live_candidate_score: float = 85.0

    minimum_liquidity_score: float = 55.0
    minimum_execution_score: float = 50.0
    minimum_greeks_score: float = 55.0
    minimum_data_confidence: float = 40.0

    reject_disallowed_strategy: bool = True
    reject_disallowed_strike: bool = True
    reject_disallowed_expiration: bool = True
    reject_disallowed_greeks: bool = True
    reject_disallowed_liquidity: bool = True

    low_confidence_penalty: float = 8.0
    poor_execution_penalty: float = 12.0
    weak_liquidity_penalty: float = 15.0
    weak_greeks_penalty: float = 10.0
    missing_component_penalty: float = 3.0

    undefined_risk_penalty: float = 20.0
    complex_strategy_penalty: float = 5.0

    maximum_total_penalty: float = 40.0
