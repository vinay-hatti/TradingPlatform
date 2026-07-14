from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionIntegrationProfile:
    valid: bool = False
    allowed: bool = True
    execution_score: float = 0.0
    execution_grade: str = "N/A"
    execution_severity: str = "UNKNOWN"
    average_shortfall_bps: float = 0.0
    average_fill_ratio: float = 0.0
    average_latency_seconds: float = 0.0
    benchmark_score: float = 0.0
    benchmark_grade: str = "N/A"
    best_benchmark: str = "UNAVAILABLE"
    recommended_venue: str = "UNAVAILABLE"
    recommended_broker: str = "UNAVAILABLE"
    routing_score: float = 0.0
    routing_grade: str = "N/A"
    routing_severity: str = "UNKNOWN"
    order_count: int = 0
    venue_count: int = 0
    broker_count: int = 0
    aggregation_profile: Any = None
    benchmark_profile: Any = None
    routing_profile: Any = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
