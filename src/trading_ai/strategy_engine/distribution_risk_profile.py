from dataclasses import dataclass, field


@dataclass
class DistributionRiskProfile:
    symbol: str
    strategy: str

    observation_count: int
    confidence_level: float
    secondary_confidence_level: float

    mean_pnl: float
    median_pnl: float
    pnl_standard_deviation: float

    mean_return: float
    annualized_return: float
    annualized_volatility: float

    downside_deviation: float
    semi_variance: float

    skewness: float
    excess_kurtosis: float

    historical_var: float
    historical_expected_shortfall: float

    parametric_var: float
    parametric_expected_shortfall: float

    monte_carlo_var: float | None
    monte_carlo_expected_shortfall: float | None

    historical_var_99: float
    historical_expected_shortfall_99: float

    probability_of_loss: float
    probability_of_large_loss: float
    probability_of_severe_loss: float
    probability_of_critical_loss: float

    average_gain: float
    average_loss: float

    gain_loss_ratio: float | None
    payoff_ratio: float | None
    profit_factor: float | None

    omega_ratio: float | None
    sortino_ratio: float | None
    gain_to_pain_ratio: float | None

    maximum_drawdown: float
    maximum_drawdown_pct: float

    average_drawdown_pct: float
    drawdown_at_risk: float
    expected_drawdown_shortfall: float

    ulcer_index: float
    pain_index: float

    tail_loss_ratio: float | None
    tail_asymmetry_ratio: float | None

    var_pct_of_capital: float
    expected_shortfall_pct_of_capital: float

    tail_risk_score: float
    tail_risk_grade: str
    risk_severity: str

    allowed: bool
    valid: bool

    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )


@dataclass
class PortfolioRiskContribution:
    position_id: str
    symbol: str
    strategy: str

    weight: float

    standalone_var: float
    marginal_var: float
    component_var: float

    standalone_expected_shortfall: float
    marginal_expected_shortfall: float
    component_expected_shortfall: float

    var_contribution_pct: float
    expected_shortfall_contribution_pct: float

    concentration_flag: bool


@dataclass
class PortfolioTailRiskProfile:
    initial_capital: float
    position_count: int
    observation_count: int

    portfolio_var: float
    portfolio_expected_shortfall: float

    portfolio_var_99: float
    portfolio_expected_shortfall_99: float

    var_pct_of_capital: float
    expected_shortfall_pct_of_capital: float

    maximum_drawdown: float
    maximum_drawdown_pct: float

    drawdown_at_risk: float
    expected_drawdown_shortfall: float

    skewness: float
    excess_kurtosis: float

    downside_deviation: float
    sortino_ratio: float | None
    omega_ratio: float | None

    largest_var_contributor: str
    largest_es_contributor: str

    risk_concentration_score: float
    diversification_benefit: float

    contributions: list[PortfolioRiskContribution]

    tail_risk_score: float
    tail_risk_grade: str
    risk_severity: str

    allowed: bool
    valid: bool

    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )
