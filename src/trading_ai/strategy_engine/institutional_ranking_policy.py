from dataclasses import dataclass


@dataclass(frozen=True)
class InstitutionalRankingPolicy:
    """
    Cross-opportunity institutional ranking policy.
    """

    # --------------------------------------------
    # Ranking weights — must total 1.00
    # --------------------------------------------

    strategy_score_weight: float = 0.40
    readiness_weight: float = 0.10
    confidence_weight: float = 0.10
    expected_return_weight: float = 0.10
    probability_weight: float = 0.07
    capital_efficiency_weight: float = 0.08
    liquidity_execution_weight: float = 0.07
    portfolio_fit_weight: float = 0.04
    diversification_weight: float = 0.04

    # --------------------------------------------
    # Minimum quality requirements
    # --------------------------------------------

    minimum_strategy_score: float = 65.0
    minimum_ranking_score: float = 60.0

    minimum_liquidity_score: float = 55.0
    minimum_execution_score: float = 50.0
    minimum_data_confidence: float = 40.0

    paper_trading_score: float = 70.0
    live_candidate_score: float = 82.0
    elite_candidate_score: float = 90.0

    # --------------------------------------------
    # Diversification limits
    # --------------------------------------------

    maximum_opportunities_per_symbol: int = 1
    maximum_opportunities_per_sector: int = 2
    maximum_same_direction: int = 3
    maximum_same_strategy: int = 2
    maximum_same_correlation_group: int = 2

    # --------------------------------------------
    # Concentration penalties
    # --------------------------------------------

    duplicate_symbol_penalty: float = 25.0
    sector_concentration_penalty: float = 8.0
    direction_concentration_penalty: float = 6.0
    strategy_concentration_penalty: float = 5.0
    correlation_concentration_penalty: float = 10.0

    # --------------------------------------------
    # Quality penalties
    # --------------------------------------------

    low_confidence_penalty: float = 8.0
    weak_liquidity_penalty: float = 12.0
    weak_execution_penalty: float = 10.0
    undefined_risk_penalty: float = 20.0
    complex_strategy_penalty: float = 4.0
    missing_pop_penalty: float = 2.0

    maximum_total_penalty: float = 50.0

    # --------------------------------------------
    # Candidate output
    # --------------------------------------------

    shortlist_size: int = 10
    live_shortlist_size: int = 5

    reject_disallowed_opportunities: bool = True
    reject_undefined_risk: bool = True

    def weights(self) -> dict[str, float]:
        return {
            "strategy_score": self.strategy_score_weight,
            "readiness": self.readiness_weight,
            "confidence": self.confidence_weight,
            "expected_return": self.expected_return_weight,
            "probability": self.probability_weight,
            "capital_efficiency": self.capital_efficiency_weight,
            "liquidity_execution": (
                self.liquidity_execution_weight
            ),
            "portfolio_fit": self.portfolio_fit_weight,
            "diversification": self.diversification_weight,
        }

    def validate(self) -> None:
        weights = self.weights()

        for name, value in weights.items():
            if value < 0:
                raise ValueError(
                    f"Ranking weight '{name}' cannot be negative"
                )

        total = sum(weights.values())

        if abs(total - 1.0) > 0.000001:
            raise ValueError(
                "Institutional ranking weights must total 1.00; "
                f"received {total:.6f}"
            )

        if self.shortlist_size <= 0:
            raise ValueError(
                "shortlist_size must be greater than zero"
            )

        if self.live_shortlist_size <= 0:
            raise ValueError(
                "live_shortlist_size must be greater than zero"
            )
