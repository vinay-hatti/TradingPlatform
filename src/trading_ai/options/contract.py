from dataclasses import dataclass
from datetime import date


@dataclass
class OptionContract:
    underlying_symbol: str
    option_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float

    bid: float
    ask: float
    mid: float
    last: float

    volume: int
    open_interest: int

    implied_volatility: float

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    @property
    def spread(self):
        return max(float(self.ask) - float(self.bid), 0.0)

    @property
    def spread_pct(self):
        if self.mid <= 0:
            return 0.0
        return self.spread / self.mid
