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
    contract_ticker: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    price_source: str = ""
    option_data_source: str = ""
    quote_timestamp: str = ""
    open_interest: int = 0
    option_volume: int = 0
    spread_pct: float = 0.0
    contract_selection_score: float = 0.0
    liquidity_score: float = 0.0
    delta_selection_score: float = 0.0
    expiration_selection_score: float = 0.0
    strike_selection_score: float = 0.0
    spread_selection_score: float = 0.0
    open_interest_selection_score: float = 0.0
    volume_selection_score: float = 0.0
    expiry_source: str = "STANDARD_FRIDAY_PROXY"
    portfolio_penalty: float = 0.0
    portfolio_notes: list = field(default_factory=list)
    trade_notes: list = field(default_factory=list)
