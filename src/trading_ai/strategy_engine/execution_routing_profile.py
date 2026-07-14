from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionRouteRecommendation:
    route_type: str = "VENUE"
    route_name: str = "UNKNOWN"
    rank: int = 0
    order_count: int = 0
    route_score: float = 0.0
    confidence_score: float = 0.0
    average_shortfall_bps: float = 0.0
    average_fill_ratio: float = 0.0
    average_latency_seconds: float = 0.0
    average_spread_bps: float = 0.0
    shortfall_volatility_bps: float = 0.0
    recommended: bool = False
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRoutingProfile:
    recommended_venue: str = "UNAVAILABLE"
    recommended_broker: str = "UNAVAILABLE"
    venue_confidence_score: float = 0.0
    broker_confidence_score: float = 0.0
    routing_score: float = 0.0
    routing_grade: str = "N/A"
    routing_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    venue_recommendations: tuple[ExecutionRouteRecommendation, ...] = ()
    broker_recommendations: tuple[ExecutionRouteRecommendation, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
