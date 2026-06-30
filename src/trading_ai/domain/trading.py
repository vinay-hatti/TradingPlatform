from dataclasses import dataclass


@dataclass(frozen=True)
class TradeRecommendation:

    symbol: str

    signal: str  # CALL | PUT
    strategy: str

    strike: float
    expiry: str

    score: float
    confidence: float

    expected_move: float
    regime: str

    price: float
    delta: float


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str  # BUY | SELL
    quantity: int
    order_type: str  # MARKET | LIMIT
