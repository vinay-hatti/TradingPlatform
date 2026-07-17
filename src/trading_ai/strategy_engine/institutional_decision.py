from dataclasses import dataclass, field
from typing import Any


@dataclass
class InstitutionalDecision:
    symbol: str

    decision_id: str

    action: str
    readiness: str

    selected: bool
    allowed: bool

    rank: int | None
    ranking_score: float
    strategy_score: float

    direction: str
    strategy: str
    market_regime: str
    volatility_regime: str

    underlying_price: float

    expiry: str
    dte: int

    strike: float | None
    long_strike: float | None
    short_strike: float | None

    option_symbol: str

    contracts: int

    capital_required: float
    maximum_loss: float
    expected_profit: float
    expected_return_pct: float

    # -------------------------------------------------
    # Probability and expected-value analytics
    # -------------------------------------------------

    probability_of_profit: float | None

    expected_value: float
    expected_return_on_risk: float

    probability_of_max_profit: float | None
    probability_of_max_loss: float | None

    probability_profit_target: float | None
    probability_stop_loss: float | None

    value_at_risk_95: float
    conditional_value_at_risk_95: float

    probability_method: str
    probability_simulation_count: int
    probability_confidence_score: float
    probability_confidence_grade: str

    stress_score: float
    stress_grade: str
    stress_risk_severity: str

    worst_scenario_name: str
    worst_scenario_pnl: float

    maximum_stress_loss: float
    maximum_stress_loss_pct_of_capital: float
    maximum_stress_loss_pct_of_maximum_loss: float | None

    scenario_allowed: bool

    # -------------------------------------------------
    # Expected move
    # -------------------------------------------------

    expected_move: float
    expected_move_pct: float
    expected_range_low: float
    expected_range_high: float

    # -------------------------------------------------
    # Greeks
    # -------------------------------------------------

    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float

    # -------------------------------------------------
    # Quality scores
    # -------------------------------------------------

    liquidity_score: float
    execution_score: float
    greeks_score: float
    data_confidence_score: float
    portfolio_fit_score: float

    premium_type: str
    risk_profile: str
    complexity: str

    sector: str
    industry: str
    correlation_group: str

    primary_reason: str
    recommendation: str

    # -------------------------------------------------
    # Phase 3 distribution and tail-risk analytics
    # Optional defaults preserve pre-Phase-3 construction APIs.
    # -------------------------------------------------

    distribution_observation_count: int = 0

    historical_var_95: float = 0.0
    historical_expected_shortfall_95: float = 0.0

    parametric_var_95: float = 0.0
    parametric_expected_shortfall_95: float = 0.0

    historical_var_99: float = 0.0
    historical_expected_shortfall_99: float = 0.0

    downside_deviation: float = 0.0
    skewness: float = 0.0
    excess_kurtosis: float = 0.0

    probability_of_large_loss: float = 0.0
    probability_of_severe_loss: float = 0.0
    probability_of_critical_loss: float = 0.0

    drawdown_at_risk: float = 0.0
    expected_drawdown_shortfall: float = 0.0

    ulcer_index: float = 0.0
    pain_index: float = 0.0

    omega_ratio: float | None = None
    sortino_ratio: float | None = None
    gain_to_pain_ratio: float | None = None

    tail_risk_score: float = 0.0
    tail_risk_grade: str = "N/A"
    tail_risk_severity: str = "UNKNOWN"

    distribution_risk_allowed: bool = False

    # -------------------------------------------------
    # Phase 4 risk-surface and sensitivity analytics
    # Optional defaults preserve all earlier construction APIs.
    # -------------------------------------------------

    risk_surface_point_count: int = 0
    risk_surface_worst_case_pnl: float = 0.0
    risk_surface_best_case_pnl: float = 0.0
    risk_surface_base_case_pnl: float = 0.0
    risk_surface_maximum_loss_pct_of_capital: float = 0.0
    risk_surface_maximum_gain_pct_of_capital: float = 0.0

    risk_surface_worst_price_shock_pct: float = 0.0
    risk_surface_worst_volatility_shock: float = 0.0
    risk_surface_worst_time_offset_days: int = 0

    delta_gamma_error_estimate: float = 0.0
    nonlinear_exposure_score: float = 0.0
    gamma_risk_score: float = 0.0
    vega_risk_score: float = 0.0
    theta_risk_score: float = 0.0

    risk_surface_score: float = 0.0
    risk_surface_grade: str = "N/A"
    risk_surface_severity: str = "UNKNOWN"
    risk_surface_allowed: bool = False


    # -------------------------------------------------
    # Phase 5 portfolio optimization recommendation
    # -------------------------------------------------

    optimization_selected: bool = False
    optimized_allocation_dollars: float = 0.0
    optimized_allocation_weight_pct: float = 0.0
    optimized_allocation_multiplier: float = 0.0
    optimized_expected_profit: float = 0.0
    optimized_maximum_loss: float = 0.0
    optimization_marginal_score: float = 0.0
    optimization_status: str = "UNAVAILABLE"

    frontier_recommended: bool = False
    frontier_point_id: str | None = None
    frontier_confidence_score: float = 0.0
    frontier_recommendation_grade: str = "N/A"
    frontier_policy_applied: bool = False

    # -------------------------------------------------
    # Phase 7 walk-forward validation analytics
    # -------------------------------------------------

    walk_forward_validated: bool = False
    walk_forward_allowed: bool = True
    walk_forward_score: float = 0.0
    walk_forward_grade: str = "N/A"
    walk_forward_severity: str = "UNKNOWN"
    walk_forward_oos_return: float = 0.0
    walk_forward_oos_sharpe: float = 0.0
    walk_forward_worst_drawdown_pct: float = 0.0
    walk_forward_parameter_stability: float = 0.0
    walk_forward_profile: Any = None

    detected_market_regime: str = "UNKNOWN"
    forecast_market_regime: str = "UNKNOWN"
    portfolio_market_regime: str = "UNKNOWN"
    market_regime_score: float = 0.0
    market_regime_confidence: float = 0.0
    market_regime_strategy_adjustment: float = 0.0
    market_regime_ranking_adjustment: float = 0.0
    market_regime_alignment: str = "NEUTRAL"
    market_regime_allowed: bool = True
    market_regime_integration_profile: Any = None

    # -------------------------------------------------
    # Phase 9 execution analytics and routing intelligence
    # -------------------------------------------------

    execution_analytics_valid: bool = False
    execution_analytics_allowed: bool = True
    execution_analytics_score: float = 0.0
    execution_analytics_grade: str = "N/A"
    execution_analytics_severity: str = "UNKNOWN"
    execution_shortfall_bps: float = 0.0
    execution_fill_ratio: float = 0.0
    execution_latency_seconds: float = 0.0
    execution_benchmark_score: float = 0.0
    execution_best_benchmark: str = "UNAVAILABLE"
    recommended_execution_venue: str = "UNAVAILABLE"
    recommended_execution_broker: str = "UNAVAILABLE"
    execution_routing_score: float = 0.0
    execution_integration_profile: Any = None

    # -------------------------------------------------
    # Phase 9 Step 5 execution governance
    # -------------------------------------------------

    execution_governance_valid: bool = False
    execution_governance_allowed: bool = True
    execution_governance_score: float = 0.0
    execution_governance_grade: str = "N/A"
    execution_governance_severity: str = "UNKNOWN"
    execution_governance_aggregate_psi: float = 0.0
    execution_governance_recommendation: str = "UNAVAILABLE"
    execution_route_registry_available: bool = False
    execution_active_route_version: str = "UNAVAILABLE"
    execution_champion_route_version: str = "UNAVAILABLE"
    execution_challenger_route_version: str = "UNAVAILABLE"
    execution_route_promotion_recommended: bool = False
    execution_governance_integration_profile: Any = None

    # -------------------------------------------------
    # Phase 10 adaptive strategy and ensemble intelligence
    # -------------------------------------------------

    phase10_valid: bool = False
    phase10_allowed: bool = True
    adaptive_strategy_selected: str = "UNAVAILABLE"
    adaptive_strategy_score: float = 0.0
    adaptive_strategy_confidence: float = 0.0
    ensemble_selected_strategy: str = "UNAVAILABLE"
    ensemble_selected_direction: str = "NEUTRAL"
    ensemble_decision_score: float = 0.0
    ensemble_meta_confidence: float = 0.0
    ensemble_consensus_ratio: float = 0.0
    dynamic_strategy_weight: float = 0.0
    online_adaptation_score: float = 0.0
    learning_state_version: str = "UNAVAILABLE"
    learning_state_champion_version: str = "UNAVAILABLE"
    learning_state_challenger_version: str = "UNAVAILABLE"
    phase10_grade: str = "N/A"
    phase10_severity: str = "UNKNOWN"
    phase10_recommendation: str = "UNAVAILABLE"
    phase10_decision_integration_profile: Any = None

    # -------------------------------------------------
    # Phase 6 probability calibration analytics
    # -------------------------------------------------

    raw_probability_of_profit: float | None = None
    calibrated_probability_of_profit: float | None = None
    probability_calibration_adjustment: float = 0.0
    probability_calibration_segment: str = "UNAVAILABLE"
    probability_calibration_model_version: str = "UNAVAILABLE"
    probability_calibration_method: str = "IDENTITY"
    probability_calibration_score: float = 0.0
    probability_calibration_grade: str = "N/A"
    probability_calibration_severity: str = "UNKNOWN"
    probability_calibration_allowed: bool = True
    probability_calibration_profile: Any = None

    calibration_adjusted_ranking_score: float = 0.0
    calibration_ranking_adjustment: float = 0.0
    probability_calibration_ranking_allowed: bool = True
    probability_calibration_ranking_profile: Any = None

    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    strengths: list[str] = field(
        default_factory=list
    )

    weaknesses: list[str] = field(
        default_factory=list
    )

    score_breakdown: Any = None
    ranking_breakdown: Any = None

    payoff_profile: Any = None
    probability_profile: Any = None
    portfolio_position: Any = None
    scenario_profile: Any = None
    distribution_risk_profile: Any = None
    risk_surface_profile: Any = None

    metadata: dict = field(
        default_factory=dict
    )

    def __post_init__(self):
        self.symbol = str(
            self.symbol or ""
        ).upper()

        self.strategy = str(
            self.strategy or ""
        ).upper()

        self.direction = str(
            self.direction or "NEUTRAL"
        ).upper()

        self.market_regime = str(
            self.market_regime or "UNKNOWN"
        ).upper()

        self.volatility_regime = str(
            self.volatility_regime or "UNKNOWN"
        ).upper()

        self.action = str(
            self.action or "NO_ACTION"
        ).upper()

        self.readiness = str(
            self.readiness or "RESEARCH_ONLY"
        ).upper()

        self.probability_method = str(
            self.probability_method or "UNAVAILABLE"
        ).upper()

        self.probability_confidence_grade = str(
            self.probability_confidence_grade or "N/A"
        ).upper()

        self.tail_risk_grade = str(
            self.tail_risk_grade or "N/A"
        ).upper()

        self.tail_risk_severity = str(
            self.tail_risk_severity or "UNKNOWN"
        ).upper()

        self.risk_surface_grade = str(
            self.risk_surface_grade or "N/A"
        ).upper()

        self.optimization_status = str(
            self.optimization_status or "UNAVAILABLE"
        ).upper()

        self.frontier_recommendation_grade = str(
            self.frontier_recommendation_grade or "N/A"
        ).upper()

        self.walk_forward_grade = str(self.walk_forward_grade or "N/A").upper()
        self.walk_forward_severity = str(self.walk_forward_severity or "UNKNOWN").upper()

        self.execution_analytics_grade = str(self.execution_analytics_grade or "N/A").upper()
        self.execution_analytics_severity = str(self.execution_analytics_severity or "UNKNOWN").upper()

        self.adaptive_strategy_selected = str(self.adaptive_strategy_selected or "UNAVAILABLE").upper()
        self.ensemble_selected_strategy = str(self.ensemble_selected_strategy or "UNAVAILABLE").upper()
        self.ensemble_selected_direction = str(self.ensemble_selected_direction or "NEUTRAL").upper()
        self.phase10_grade = str(self.phase10_grade or "N/A").upper()
        self.phase10_severity = str(self.phase10_severity or "UNKNOWN").upper()

        self.risk_surface_severity = str(
            self.risk_surface_severity or "UNKNOWN"
        ).upper()

        self.rejection_reasons = list(
            self.rejection_reasons or []
        )

        self.warnings = list(
            self.warnings or []
        )

        self.strengths = list(
            self.strengths or []
        )

        self.weaknesses = list(
            self.weaknesses or []
        )

        self.metadata = dict(
            self.metadata or {}
        )
