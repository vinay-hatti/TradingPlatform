from dataclasses import dataclass


@dataclass
class InstitutionalRankBreakdown:
    strategy_score: float
    readiness_score: float
    confidence_score: float
    expected_return_score: float
    probability_score: float
    capital_efficiency_score: float
    liquidity_execution_score: float
    portfolio_fit_score: float
    diversification_score: float

    weighted_strategy_score: float
    weighted_readiness_score: float
    weighted_confidence_score: float
    weighted_expected_return_score: float
    weighted_probability_score: float
    weighted_capital_efficiency_score: float
    weighted_liquidity_execution_score: float
    weighted_portfolio_fit_score: float
    weighted_diversification_score: float

    raw_ranking_score: float

    hard_penalty: float
    concentration_penalty: float
    quality_penalty: float
    total_penalty: float

    final_ranking_score: float
