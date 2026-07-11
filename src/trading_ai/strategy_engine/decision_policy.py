from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionPolicy:
    """
    Final Phase 12 decision acceptance policy.
    """

    minimum_technical_score: float = 50.0
    minimum_strategy_score: float = 65.0
    minimum_ranking_score: float = 60.0

    minimum_volatility_confidence: float = 30.0
    minimum_expected_move_confidence: float = 40.0

    minimum_liquidity_score: float = 55.0
    minimum_execution_score: float = 50.0
    minimum_greeks_score: float = 55.0

    paper_trade_score: float = 70.0
    live_candidate_score: float = 85.0
    priority_candidate_score: float = 92.0

    maximum_candidates_per_symbol: int = 10
    maximum_total_candidates: int = 100

    require_price_history: bool = True
    require_option_chain: bool = True

    require_allowed_strategy: bool = True
    require_allowed_expiration: bool = True
    require_allowed_strike: bool = True
    require_allowed_greeks: bool = True
    require_allowed_liquidity: bool = True

    reject_undefined_risk: bool = True
    reject_missing_maximum_loss: bool = True

    allow_missing_probability_of_profit: bool = True
    allow_missing_payoff_profile: bool = True

    stop_after_first_valid_strike_per_strategy: bool = False

    def validate(self) -> None:
        score_fields = {
            "minimum_technical_score":
                self.minimum_technical_score,
            "minimum_strategy_score":
                self.minimum_strategy_score,
            "minimum_ranking_score":
                self.minimum_ranking_score,
            "minimum_volatility_confidence":
                self.minimum_volatility_confidence,
            "minimum_expected_move_confidence":
                self.minimum_expected_move_confidence,
            "minimum_liquidity_score":
                self.minimum_liquidity_score,
            "minimum_execution_score":
                self.minimum_execution_score,
            "minimum_greeks_score":
                self.minimum_greeks_score,
            "paper_trade_score":
                self.paper_trade_score,
            "live_candidate_score":
                self.live_candidate_score,
            "priority_candidate_score":
                self.priority_candidate_score,
        }

        for name, value in score_fields.items():
            if value < 0 or value > 100:
                raise ValueError(
                    f"{name} must be between 0 and 100"
                )

        if self.maximum_candidates_per_symbol <= 0:
            raise ValueError(
                "maximum_candidates_per_symbol must be positive"
            )

        if self.maximum_total_candidates <= 0:
            raise ValueError(
                "maximum_total_candidates must be positive"
            )
