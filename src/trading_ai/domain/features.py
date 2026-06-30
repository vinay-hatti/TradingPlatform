from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str

    close: float
    atr14: float
    atr14_mean: float

    ema20: float
    rsi14: float
    macd: float

    market_regime: str

    expected_move_1d: float
