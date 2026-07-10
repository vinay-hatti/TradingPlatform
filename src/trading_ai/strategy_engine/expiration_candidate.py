from dataclasses import dataclass, field


@dataclass
class ExpirationCandidate:
    symbol: str
    strategy: str

    expiry: str
    dte: int

    underlying_price: float

    contracts_available: int
    avg_volume: float
    avg_open_interest: float
    avg_spread_pct: float
    avg_iv: float

    avg_abs_delta: float
    avg_abs_theta: float
    avg_vega: float

    expected_move: float
    expected_move_pct: float

    dte_score: float
    liquidity_score: float
    theta_score: float
    volatility_score: float
    expected_move_score: float
    composite_score: float

    reason: str
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
