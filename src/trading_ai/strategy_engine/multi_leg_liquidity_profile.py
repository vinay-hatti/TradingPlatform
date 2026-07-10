from dataclasses import dataclass, field

from trading_ai.strategy_engine.liquidity_profile import LiquidityProfile


@dataclass
class MultiLegLiquidityProfile:
    symbol: str
    strategy: str

    legs: list[LiquidityProfile]

    leg_count: int
    requested_contracts: int

    package_mid: float
    estimated_package_price: float

    total_absolute_spread: float
    package_spread_pct: float

    minimum_leg_liquidity_score: float
    average_leg_liquidity_score: float
    package_liquidity_score: float
    execution_score: float

    estimated_round_trip_slippage: float
    estimated_round_trip_slippage_pct: float

    weakest_leg: str
    liquidity_grade: str
    execution_quality: str

    allowed: bool
    reason: str
    warnings: list[str] = field(default_factory=list)
