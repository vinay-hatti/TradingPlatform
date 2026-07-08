from dataclasses import dataclass, field


@dataclass
class LiveTradeCandidate:
    symbol: str
    signal: str
    strategy: str
    sector: str

    ai_score: float
    confidence: str
    ranking_reason: str

    underlying_price: float
    strike: float
    expiry: str
    dte: int

    option_entry: float
    target_price: float
    stop_price: float

    contracts: int
    estimated_cost: float
    max_risk: float
    estimated_reward: float
    reward_risk_ratio: float

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    volatility: float

    market_regime: str
    technical_score: float
    greeks_score: float
    regime_score: float
    volatility_score: float
    risk_score: float

    portfolio_penalty: float = 0.0
    portfolio_notes: list = field(default_factory=list)
    trade_notes: list = field(default_factory=list)
