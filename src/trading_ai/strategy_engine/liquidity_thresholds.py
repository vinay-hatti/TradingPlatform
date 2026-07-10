from dataclasses import dataclass


@dataclass
class LiquidityThresholds:
    min_volume: int = 50
    min_open_interest: int = 100

    max_spread_pct: float = 0.30
    preferred_spread_pct: float = 0.10

    min_bid: float = 0.01
    min_mid: float = 0.05

    min_quoted_depth: int = 1

    max_contracts_to_volume_ratio: float = 0.10
    max_contracts_to_open_interest_ratio: float = 0.02

    minimum_liquidity_score: float = 55.0
    minimum_execution_score: float = 50.0

    reject_zero_bid: bool = True
    reject_crossed_market: bool = True
    reject_locked_market: bool = False
