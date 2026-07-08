from dataclasses import dataclass


@dataclass
class PortfolioPosition:

    symbol: str

    strategy: str

    signal: str

    sector: str

    contracts: int

    avg_price: float

    current_price: float

    market_value: float

    delta: float

    gamma: float

    theta: float

    vega: float

    rho: float

    entry_date: str
