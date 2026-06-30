from dataclasses import dataclass


@dataclass
class OptionContract:
    symbol: str
    expiration: str

    option_type: str

    strike: float

    bid: float

    ask: float

    last: float

    volume: int

    open_interest: int

    implied_volatility: float

    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
