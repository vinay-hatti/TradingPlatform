from dataclasses import dataclass, field


@dataclass
class LiquidityProfile:
    symbol: str
    option_symbol: str

    bid: float
    ask: float
    mid: float
    last: float

    volume: int
    open_interest: int

    absolute_spread: float
    spread_pct: float

    bid_size: int
    ask_size: int
    quoted_depth: int

    requested_contracts: int
    estimated_capacity: int

    volume_score: float
    open_interest_score: float
    spread_score: float
    depth_score: float
    capacity_score: float
    quote_quality_score: float

    liquidity_score: float
    execution_score: float

    estimated_buy_price: float
    estimated_sell_price: float
    estimated_round_trip_slippage: float
    estimated_round_trip_slippage_pct: float

    liquidity_grade: str
    execution_quality: str
    allowed: bool

    reason: str
    warnings: list[str] = field(default_factory=list)
