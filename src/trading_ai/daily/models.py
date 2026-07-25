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
    base_ai_score: float = 0.0
    dealer_context_status: str = "DISABLED"
    dealer_snapshot_date: str = ""
    dealer_snapshot_age_days: int = -1
    institutional_positioning_score: float = 0.0
    positioning_label: str = "UNAVAILABLE"
    gamma_regime: str = "UNAVAILABLE"
    gamma_flip: float | None = None
    spot_vs_gamma_flip_pct: float | None = None
    primary_call_wall: float | None = None
    primary_put_wall: float | None = None
    distance_to_call_wall_pct: float | None = None
    distance_to_put_wall_pct: float | None = None
    dealer_hedging_pressure: float = 0.0
    range_probability: float = 0.0
    breakout_probability: float = 0.0
    breakdown_probability: float = 0.0
    volatility_expansion_probability: float = 0.0
    market_structure_confidence: float = 0.0
    directional_alignment_probability: float = 0.0
    dealer_score_adjustment: float = 0.0
    dealer_context_warning: str = ""
