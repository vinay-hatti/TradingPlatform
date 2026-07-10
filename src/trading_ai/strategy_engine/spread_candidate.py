from dataclasses import dataclass, field


@dataclass
class SpreadCandidate:
    symbol: str
    strategy: str
    option_type: str

    short_strike: float
    long_strike: float
    expiry: str
    dte: int

    credit_or_debit: float
    width: float
    max_profit: float
    max_loss: float

    short_delta: float
    long_delta: float
    net_delta: float
    net_theta: float
    net_vega: float

    liquidity_score: float
    greek_score: float
    width_score: float
    risk_reward_score: float
    composite_score: float

    reason: str
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
