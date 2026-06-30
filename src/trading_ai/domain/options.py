from dataclasses import dataclass


@dataclass(frozen=True)
class OptionContract:

    underlying: str

    option_symbol: str

    strike: float

    expiry: str

    option_type: str

    bid: float

    ask: float

    last: float

    volume: int

    open_interest: int

    implied_volatility: float

    delta: float

    gamma: float

    theta: float

    vega: float

    rho: float
