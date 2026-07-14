from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionBenchmarkPolicy:
    minimum_orders: int = 3
    maximum_average_shortfall_bps: float = 25.0
    severe_average_shortfall_bps: float = 50.0
    critical_average_shortfall_bps: float = 100.0
    minimum_benchmark_score: float = 50.0
    reject_critical_benchmark: bool = False
    reject_invalid_profile: bool = False
    decision_price_enabled: bool = True
    arrival_price_enabled: bool = True
    midpoint_enabled: bool = True
    vwap_enabled: bool = True
