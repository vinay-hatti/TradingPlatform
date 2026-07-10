from dataclasses import dataclass


@dataclass
class VolatilityProfile:
    symbol: str

    hv20: float
    hv30: float
    hv60: float
    hv90: float

    current_iv: float
    iv_rank: float
    iv_percentile: float

    iv_hv_ratio: float
    volatility_regime: str
    volatility_signal: str

    expected_move_1d: float
    expected_move_5d: float
    expected_move_10d: float
    expected_move_30d: float

    confidence: float
