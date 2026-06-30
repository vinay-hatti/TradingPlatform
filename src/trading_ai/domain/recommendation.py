from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class TradeRecommendation:

    symbol: str

    signal: str

    strategy: str

    strike: float

    expiry: str

    score: float

    confidence: float

    expected_move: float

    regime: str

    price: float

    delta: float

    option: Optional[object] = None
