from dataclasses import dataclass


@dataclass
class DailyCandidate:
    symbol: str
    signal: str
    strategy: str
    close: float
    score: float
    call_score: float
    put_score: float
    market_regime: str

    strike: float
    expiry: str
    option_price: float

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    volatility: float
    dte: int

    final_score: float
