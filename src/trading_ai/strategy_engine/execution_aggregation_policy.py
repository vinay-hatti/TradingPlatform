from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionAggregationPolicy:
    minimum_orders_per_group: int = 2
    minimum_venues_for_comparison: int = 2
    maximum_average_shortfall_bps: float = 35.0
    severe_average_shortfall_bps: float = 75.0
    critical_average_shortfall_bps: float = 150.0
    maximum_average_spread_bps: float = 100.0
    maximum_average_delay_seconds: float = 30.0
    minimum_average_fill_ratio: float = 0.90
    minimum_benchmark_score: float = 60.0
    reject_critical_execution: bool = False
    reject_invalid_profile: bool = False
    shortfall_weight: float = 0.35
    fill_weight: float = 0.20
    latency_weight: float = 0.15
    spread_weight: float = 0.15
    consistency_weight: float = 0.15
