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
    base_trend_score_adjustment: float = 0.0
    transition_context_status: str = "DISABLED"
    transition_snapshot_date: str = ""
    transition_snapshot_age_days: int = -1
    transition_state: str = "UNAVAILABLE"
    transition_direction: str = "UNAVAILABLE"
    breakout_state: str = "UNAVAILABLE"
    channel_position_pct: float = 50.0
    momentum_acceleration_score: float = 0.0
    volatility_state: str = "UNAVAILABLE"
    volatility_percentile: float = 50.0
    reversal_risk_score: float = 0.0
    exhaustion_risk_score: float = 0.0
    transition_confirmation_score: float = 50.0
    transition_score_adjustment: float = 0.0
    combined_trend_score_adjustment: float = 0.0
    transition_context_warning: str = ""
    trend_context_warning: str = ""
    trend_sector: str = "Unknown"
    trend_sector_etf: str = ""
    relative_strength_multiplier: float = 1.0
    forecast_context_status: str = "DISABLED"
    forecast_snapshot_date: str = ""
    forecast_snapshot_age_days: int = -1
    forecast_direction: str = "UNAVAILABLE"
    forecast_horizon_days: int = 10
    forecast_requested_horizon_days: int = 10
    forecast_resolved_horizon_days: int | None = None
    forecast_horizon_distance_days: int | None = None
    forecast_horizon_resolution: str = "UNRESOLVED"
    continuation_probability: float = 50.0
    reversal_probability: float = 50.0
    forecast_confidence_score: float = 0.0
    forecast_confidence_grade: str = "UNAVAILABLE"
    forecast_expected_return_pct: float = 0.0
    forecast_expected_volatility_pct: float = 0.0
    forecast_persistence_days: int = 0
    forecast_score_adjustment: float = 0.0
    forecast_context_warning: str = ""
    institutional_context_status: str = "DISABLED"
    institutional_snapshot_date: str = ""
    institutional_snapshot_age_days: int = -1
    participation_score: float = 50.0
    participation_grade: str = "UNAVAILABLE"
    participation_state: str = "UNAVAILABLE"
    leadership_score: float = 50.0
    leadership_grade: str = "UNAVAILABLE"
    leadership_state: str = "UNAVAILABLE"
    institutional_trend_quality_score: float = 50.0
    institutional_conviction_score: float = 50.0
    deterioration_risk_score: float = 50.0
    deterioration_state: str = "UNAVAILABLE"
    breadth_confirmation_score: float = 50.0
    cross_asset_confirmation_score: float = 50.0
    institutional_score_adjustment: float = 0.0
    institutional_context_warning: str = ""
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
