from dataclasses import dataclass


@dataclass(frozen=True)
class OptionContract:

    symbol: str
    strike: float
    expiry: str

    delta: float
    volume: float

    implied_volatility: float
    expected_move_1d: float
