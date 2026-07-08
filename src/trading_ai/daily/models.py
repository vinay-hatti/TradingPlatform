from dataclasses import dataclass, field


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

    sector: str = "Unknown"
    portfolio_penalty: float = 0.0
    adjusted_score: float = 0.0
    portfolio_notes: list = field(default_factory=list)

    ai_score: float = 0.0
    technical_score: float = 0.0
    greeks_score: float = 0.0
    regime_score: float = 0.0
    volatility_score: float = 0.0
    risk_score: float = 0.0
    ranking_reason: str = ""
