from dataclasses import dataclass
@dataclass(frozen=True)
class TrendTransitionPolicy:
    channel_lookback: int = 63
    breakout_buffer_pct: float = 0.25
    momentum_fast: int = 5
    momentum_slow: int = 20
    volatility_lookback: int = 126
    minimum_history_days: int = 65
    maximum_transition_adjustment: float = 2.0
