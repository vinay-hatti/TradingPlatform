from dataclasses import dataclass, field

from trading_ai.strategy_engine.expected_move_source import ExpectedMoveSource


@dataclass
class ExpectedMoveProfile:
    symbol: str

    underlying_price: float
    horizon_days: int

    implied_volatility: float
    historical_volatility: float
    atr: float

    iv_move: float
    straddle_move: float
    historical_move: float
    atr_move: float

    blended_move: float
    blended_move_pct: float

    lower_bound: float
    upper_bound: float

    lower_bound_2sigma: float
    upper_bound_2sigma: float

    daily_move: float
    weekly_move: float
    monthly_move: float

    source_count: int
    source_agreement_score: float
    confidence_score: float
    confidence_grade: str

    move_regime: str
    expansion_signal: str

    dominant_source: str
    sources: list[ExpectedMoveSource] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
