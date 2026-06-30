from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:

    symbol: str

    action: str  # CALL | PUT | NO_TRADE
    score: float

    confidence: float

    regime: str

    expected_move: float
