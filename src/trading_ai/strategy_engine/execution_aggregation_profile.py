from dataclasses import dataclass, field
from typing import Any

from .execution_analytics_profile import ExecutionAnalyticsProfile


@dataclass(frozen=True)
class ExecutionOrderProfile:
    order_id: str = ""
    symbol: str = ""
    strategy: str = ""
    venue: str = "UNKNOWN"
    broker: str = "UNKNOWN"
    execution_profile: ExecutionAnalyticsProfile | None = None
    benchmark_price: float = 0.0
    benchmark_name: str = "DECISION_PRICE"
    benchmark_shortfall: float = 0.0
    benchmark_shortfall_bps: float = 0.0
    execution_efficiency_score: float = 0.0
    valid: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionVenueProfile:
    venue: str = "UNKNOWN"
    broker: str = "UNKNOWN"
    order_count: int = 0
    notional: float = 0.0
    average_shortfall_bps: float = 0.0
    average_arrival_slippage_bps: float = 0.0
    average_market_impact_bps: float = 0.0
    average_effective_spread_bps: float = 0.0
    average_fill_ratio: float = 0.0
    average_fill_delay_seconds: float = 0.0
    shortfall_volatility_bps: float = 0.0
    execution_score: float = 0.0
    execution_grade: str = "N/A"
    execution_severity: str = "UNKNOWN"
    rank: int = 0
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionBenchmarkProfile:
    benchmark_name: str = "DECISION_PRICE"
    order_count: int = 0
    average_shortfall_bps: float = 0.0
    median_shortfall_bps: float = 0.0
    p90_shortfall_bps: float = 0.0
    best_shortfall_bps: float = 0.0
    worst_shortfall_bps: float = 0.0
    benchmark_score: float = 0.0
    benchmark_grade: str = "N/A"
    valid: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionAggregationProfile:
    order_count: int = 0
    venue_count: int = 0
    broker_count: int = 0
    total_notional: float = 0.0
    average_shortfall_bps: float = 0.0
    average_fill_ratio: float = 0.0
    average_delay_seconds: float = 0.0
    best_venue: str = "UNAVAILABLE"
    worst_venue: str = "UNAVAILABLE"
    best_broker: str = "UNAVAILABLE"
    worst_broker: str = "UNAVAILABLE"
    aggregate_execution_score: float = 0.0
    aggregate_execution_grade: str = "N/A"
    aggregate_execution_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    orders: tuple[ExecutionOrderProfile, ...] = ()
    venues: tuple[ExecutionVenueProfile, ...] = ()
    brokers: tuple[ExecutionVenueProfile, ...] = ()
    benchmarks: tuple[ExecutionBenchmarkProfile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
