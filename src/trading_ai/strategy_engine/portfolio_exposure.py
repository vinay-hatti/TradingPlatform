from dataclasses import dataclass, field


@dataclass
class PortfolioExposure:
    initial_capital: float

    total_capital_allocated: float
    total_maximum_loss: float
    total_expected_profit: float

    exposure_pct: float
    risk_pct: float
    expected_return_on_capital_pct: float

    available_capital: float
    reserve_cash: float

    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float

    gross_delta: float
    gross_gamma: float
    gross_theta: float
    gross_vega: float

    position_count: int

    symbol_exposure: dict[str, float] = field(
        default_factory=dict
    )

    sector_exposure: dict[str, float] = field(
        default_factory=dict
    )

    strategy_exposure: dict[str, float] = field(
        default_factory=dict
    )

    direction_exposure: dict[str, float] = field(
        default_factory=dict
    )

    correlation_group_exposure: dict[str, float] = field(
        default_factory=dict
    )

    symbol_counts: dict[str, int] = field(
        default_factory=dict
    )

    sector_counts: dict[str, int] = field(
        default_factory=dict
    )

    strategy_counts: dict[str, int] = field(
        default_factory=dict
    )

    direction_counts: dict[str, int] = field(
        default_factory=dict
    )

    correlation_group_counts: dict[str, int] = field(
        default_factory=dict
    )
