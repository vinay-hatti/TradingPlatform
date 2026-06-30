from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class TradeContext:
    symbol: str

    close: float

    ema20: float
    ema50: float
    ema200: float

    rsi14: float
    atr14: float

    market_regime: str

    call_score: float
    put_score: float

    expected_move_1d: float
    em_ratio: float

    iv: float
    iv_rank: float

    option: Optional[object] = None
