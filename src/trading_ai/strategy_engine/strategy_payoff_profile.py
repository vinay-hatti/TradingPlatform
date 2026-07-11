from dataclasses import dataclass, field


@dataclass
class StrategyPayoffProfile:
    symbol: str
    strategy: str

    valuation_mode: str

    net_debit: float
    net_credit: float

    maximum_profit: float | None
    maximum_loss: float | None

    break_even_points: list[float]

    risk_reward_ratio: float | None
    return_on_risk_pct: float | None

    profit_at_current_price: float

    best_price_tested: float
    worst_price_tested: float

    best_profit_tested: float
    worst_loss_tested: float

    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float

    unlimited_profit: bool
    unlimited_loss: bool
    defined_risk: bool

    capital_required: float
    expected_profit: float
    expected_return_pct: float

    payoff_points: list[dict]

    valid: bool
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
