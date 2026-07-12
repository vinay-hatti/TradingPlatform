from dataclasses import dataclass, field


@dataclass
class ScenarioPoint:
    scenario_name: str
    scenario_description: str

    category: str
    severity: str

    base_underlying_price: float
    stressed_underlying_price: float

    base_volatility: float
    stressed_volatility: float

    base_days_to_expiry: int
    stressed_days_to_expiry: int
    days_forward: int

    base_strategy_value: float
    stressed_strategy_value: float

    entry_cash_flow: float

    stressed_pnl: float
    pnl_change_from_base: float

    return_on_capital: float
    loss_pct_of_maximum_loss: float | None

    passed: bool
    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )


@dataclass
class ScenarioAnalysisResult:
    symbol: str
    strategy: str

    underlying_price: float
    base_volatility: float
    days_to_expiry: int

    capital_required: float
    maximum_loss: float

    base_strategy_value: float
    base_pnl: float

    scenario_points: list[ScenarioPoint]

    worst_scenario_name: str
    worst_scenario_pnl: float

    best_scenario_name: str
    best_scenario_pnl: float

    maximum_stress_loss: float
    maximum_stress_loss_pct_of_capital: float
    maximum_stress_loss_pct_of_maximum_loss: float | None

    average_scenario_pnl: float
    weighted_scenario_pnl: float | None

    downside_scenario_count: int
    profitable_scenario_count: int
    failed_scenario_count: int

    stress_score: float
    stress_grade: str
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
class PortfolioScenarioPoint:
    scenario_name: str
    scenario_description: str

    total_base_value: float
    total_stressed_value: float

    total_stressed_pnl: float
    pnl_change_from_base: float

    loss_pct_of_portfolio_capital: float

    position_results: list[dict]

    passed: bool
    rejection_reasons: list[str] = field(
        default_factory=list
    )


@dataclass
class PortfolioScenarioResult:
    initial_capital: float
    position_count: int

    scenario_points: list[PortfolioScenarioPoint]

    worst_scenario_name: str
    worst_scenario_pnl: float
    worst_scenario_loss_pct: float

    best_scenario_name: str
    best_scenario_pnl: float

    maximum_stress_loss: float
    average_scenario_pnl: float

    stress_score: float
    stress_grade: str
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
