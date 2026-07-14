from dataclasses import dataclass, field


@dataclass
class RiskSurfacePoint:
    price_shock_pct: float
    volatility_shock: float
    time_offset_days: int
    approximated_pnl: float
    delta_component: float
    gamma_component: float
    vega_component: float
    theta_component: float
    rho_component: float
    shocked_underlying_price: float
    shocked_implied_volatility: float


@dataclass
class RiskAttribution:
    factor: str
    pnl: float
    contribution_pct: float
    adverse: bool


@dataclass
class RiskSurfaceProfile:
    symbol: str
    strategy: str
    underlying_price: float
    implied_volatility: float
    days_to_expiration: int
    capital_required: float
    initial_capital: float
    net_delta: float
    net_gamma: float
    net_vega: float
    net_theta: float
    net_rho: float
    point_count: int
    worst_case_pnl: float
    best_case_pnl: float
    base_case_pnl: float
    maximum_loss_pct_of_capital: float
    maximum_gain_pct_of_capital: float
    worst_price_shock_pct: float
    worst_volatility_shock: float
    worst_time_offset_days: int
    delta_gamma_error_estimate: float
    nonlinear_exposure_score: float
    gamma_risk_score: float
    vega_risk_score: float
    theta_risk_score: float
    surface_score: float
    surface_grade: str
    risk_severity: str
    allowed: bool
    valid: bool
    points: list[RiskSurfacePoint] = field(default_factory=list)
    attributions: list[RiskAttribution] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class PortfolioRiskSurfaceContribution:
    position_id: str
    symbol: str
    strategy: str
    sector: str
    correlation_group: str
    allocation_multiplier: float
    capital_required: float
    standalone_worst_case_pnl: float
    portfolio_worst_point_pnl: float
    loss_contribution_pct: float
    capital_weight_pct: float
    surface_score: float
    risk_severity: str


@dataclass
class PortfolioRiskSurfaceProfile:
    initial_capital: float
    position_count: int
    point_count: int
    worst_case_pnl: float
    best_case_pnl: float
    maximum_loss_pct_of_capital: float
    surface_score: float
    surface_grade: str
    risk_severity: str
    largest_loss_contributor: str
    allowed: bool
    valid: bool
    aggregate_points: list[RiskSurfacePoint] = field(default_factory=list)
    position_contributions: list = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    base_case_pnl: float = 0.0
    total_allocated_capital: float = 0.0
    portfolio_exposure_pct: float = 0.0
    standalone_worst_case_loss: float = 0.0
    diversification_benefit: float = 0.0
    loss_concentration_score: float = 0.0
    capital_concentration_score: float = 0.0
    effective_position_count: float = 0.0
    largest_loss_contribution_pct: float = 0.0
    largest_capital_weight_pct: float = 0.0
    worst_price_shock_pct: float = 0.0
    worst_volatility_shock: float = 0.0
    worst_time_offset_days: int = 0
    factor_attributions: list[RiskAttribution] = field(default_factory=list)
    sector_contributions: list[dict] = field(default_factory=list)
    strategy_contributions: list[dict] = field(default_factory=list)
    correlation_group_contributions: list[dict] = field(default_factory=list)
