from dataclasses import dataclass


@dataclass
class TradeRecommendation:
    symbol: str

    signal: str

    strategy: str

    strike: float

    expiry: str

    delta: float

    score: float

    expected_move: float

    regime: str

    price: float

    confidence: float
