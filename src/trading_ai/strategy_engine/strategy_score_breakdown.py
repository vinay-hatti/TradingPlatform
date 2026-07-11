from dataclasses import dataclass


@dataclass
class StrategyScoreBreakdown:
    technical_score: float
    volatility_score: float
    expected_move_score: float
    strategy_selection_score: float

    strike_score: float
    expiration_score: float
    greeks_score: float

    liquidity_score: float
    execution_score: float

    risk_reward_score: float
    data_confidence_score: float
    portfolio_fit_score: float

    weighted_technical: float
    weighted_volatility: float
    weighted_expected_move: float
    weighted_strategy_selection: float

    weighted_strike: float
    weighted_expiration: float
    weighted_greeks: float

    weighted_liquidity: float
    weighted_execution: float

    weighted_risk_reward: float
    weighted_data_confidence: float
    weighted_portfolio_fit: float

    raw_composite_score: float
    total_penalty: float
    final_composite_score: float
