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

    distribution_observation_count: int

    historical_var_95: float
    historical_expected_shortfall_95: float

    parametric_var_95: float
    parametric_expected_shortfall_95: float

    historical_var_99: float
    historical_expected_shortfall_99: float

    downside_deviation: float
    skewness: float
    excess_kurtosis: float

    probability_of_large_loss: float
    probability_of_severe_loss: float
    probability_of_critical_loss: float

    drawdown_at_risk: float
    expected_drawdown_shortfall: float

    ulcer_index: float
    pain_index: float

    omega_ratio: float | None
    sortino_ratio: float | None
    gain_to_pain_ratio: float | None

    tail_risk_score: float
    tail_risk_grade: str
    tail_risk_severity: str

    distribution_risk_allowed: bool

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
