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

    probability_of_profit: float | None

    expected_move: float
    expected_move_pct: float
    expected_range_low: float
    expected_range_high: float

    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float

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
    portfolio_position: Any = None

    metadata: dict = field(
        default_factory=dict
    )
