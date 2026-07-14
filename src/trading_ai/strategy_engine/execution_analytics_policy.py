from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionAnalyticsPolicy:
    """Institutional execution-quality limits and scoring controls."""

    maximum_slippage_bps: float = 35.0
    severe_slippage_bps: float = 75.0
    critical_slippage_bps: float = 150.0
    maximum_spread_pct: float = 0.20
    severe_spread_pct: float = 0.35
    maximum_market_impact_bps: float = 40.0
    maximum_fill_delay_seconds: float = 120.0
    minimum_fill_ratio: float = 0.90
    minimum_execution_score: float = 55.0
    reject_critical_execution: bool = False
    reject_invalid_profile: bool = False
    slippage_weight: float = 0.30
    spread_weight: float = 0.20
    impact_weight: float = 0.20
    fill_weight: float = 0.20
    latency_weight: float = 0.10

    def __post_init__(self) -> None:
        if self.maximum_slippage_bps <= 0:
            raise ValueError("maximum_slippage_bps must be positive")
        if not 0.0 <= self.maximum_spread_pct <= 1.0:
            raise ValueError("maximum_spread_pct must be between 0 and 1")
        if not 0.0 <= self.minimum_fill_ratio <= 1.0:
            raise ValueError("minimum_fill_ratio must be between 0 and 1")
        weights = (
            self.slippage_weight + self.spread_weight + self.impact_weight
            + self.fill_weight + self.latency_weight
        )
        if weights <= 0:
            raise ValueError("execution score weights must sum to a positive value")
