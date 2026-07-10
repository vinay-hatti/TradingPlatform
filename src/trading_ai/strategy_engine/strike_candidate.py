from dataclasses import dataclass, field


@dataclass
class StrikeCandidate:
    symbol: str
    strategy: str
    option_type: str

    strike: float
    expiry: str
    dte: int

    option_symbol: str
    bid: float
    ask: float
    mid: float
    last: float

    volume: int
    open_interest: int
    spread_pct: float

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float

    underlying_price: float

    moneyness_pct: float
    intrinsic_value: float
    extrinsic_value: float

    liquidity_score: float
    greek_score: float
    moneyness_score: float
    value_score: float
    risk_score: float
    composite_score: float

    reason: str
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
