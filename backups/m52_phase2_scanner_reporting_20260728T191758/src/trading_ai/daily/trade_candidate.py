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
    base_ai_score: float = 0.0
    raw_ai_score: float = 0.0
    score_capped: bool = False
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
    trend_context_status: str = "DISABLED"
    trend_snapshot_date: str = ""
    trend_snapshot_age_days: int = -1
    short_term_trend: str = "UNAVAILABLE"
    intermediate_term_trend: str = "UNAVAILABLE"
    long_term_trend: str = "UNAVAILABLE"
    trend_alignment_score: float = 50.0
    signal_trend_alignment_score: float = 50.0
    trend_quality_score: float = 50.0
    trend_confidence: float = 0.0
    trend_stage: str = "UNAVAILABLE"
    trend_age_days: int = 0
    relative_strength_vs_spy: float = 0.0
    relative_strength_vs_sector: float = 0.0
    relative_strength_grade: str = "UNAVAILABLE"
    sector_trend_alignment_score: float = 50.0
    market_trend_alignment_score: float = 50.0
    trend_score_adjustment: float = 0.0
    trend_context_warning: str = ""
    trend_sector: str = "Unknown"
    trend_sector_etf: str = ""
    relative_strength_multiplier: float = 1.0
    publication_name: str = ""
    ingestion_run_id: str = ""
    publication_status: str = ""
    published_at: str = ""
    market_as_of_date: str = ""
    market_intelligence_snapshot_timestamp: str = ""
    option_snapshot_timestamp: str = ""
    option_snapshot_id: str = ""
    option_snapshot_completeness_pct: float | None = None
    published_state_degraded: bool = False
    scanner_run_id: str = ""
    candidate_id: str = ""
    market_state_hash: str = ""
    scanner_version: str = "m47.phase5.v1"
