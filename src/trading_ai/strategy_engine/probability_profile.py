from dataclasses import dataclass, field


@dataclass
class ProbabilityProfile:
    symbol: str
    strategy: str

    underlying_price: float
    horizon_days: int

    volatility: float
    risk_free_rate: float
    dividend_yield: float

    simulation_count: int
    random_seed: int

    probability_of_profit: float
    probability_of_loss: float
    probability_of_breakeven: float

    probability_of_max_profit: float | None
    probability_of_max_loss: float | None

    probability_above_upper_breakeven: float | None
    probability_below_lower_breakeven: float | None
    probability_inside_breakevens: float | None

    probability_touch_upper: float | None
    probability_touch_lower: float | None

    probability_profit_target: float | None
    probability_stop_loss: float | None

    expected_value: float
    expected_value_per_contract: float
    expected_return_on_capital: float
    expected_return_on_risk: float

    average_profit: float
    average_loss: float

    median_pnl: float
    pnl_standard_deviation: float

    value_at_risk_95: float
    conditional_value_at_risk_95: float

    best_simulated_pnl: float
    worst_simulated_pnl: float

    expected_terminal_price: float
    median_terminal_price: float
    terminal_price_stddev: float

    lower_terminal_price_5pct: float
    upper_terminal_price_95pct: float

    confidence_score: float
    confidence_grade: str

    method: str
    valid: bool

    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
