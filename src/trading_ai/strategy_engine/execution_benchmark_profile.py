from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionBenchmarkOrderResult:
    order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    benchmark_name: str = "DECISION_PRICE"
    benchmark_price: float = 0.0
    average_fill_price: float = 0.0
    shortfall: float = 0.0
    shortfall_bps: float = 0.0
    notional: float = 0.0
    valid: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionBenchmarkSummary:
    benchmark_name: str = "DECISION_PRICE"
    order_count: int = 0
    average_shortfall_bps: float = 0.0
    median_shortfall_bps: float = 0.0
    p90_shortfall_bps: float = 0.0
    shortfall_volatility_bps: float = 0.0
    best_shortfall_bps: float = 0.0
    worst_shortfall_bps: float = 0.0
    benchmark_score: float = 0.0
    benchmark_grade: str = "N/A"
    benchmark_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionBenchmarkProfile:
    order_count: int = 0
    benchmark_count: int = 0
    best_benchmark: str = "UNAVAILABLE"
    worst_benchmark: str = "UNAVAILABLE"
    aggregate_benchmark_score: float = 0.0
    aggregate_benchmark_grade: str = "N/A"
    aggregate_benchmark_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    order_results: tuple[ExecutionBenchmarkOrderResult, ...] = ()
    summaries: tuple[ExecutionBenchmarkSummary, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
