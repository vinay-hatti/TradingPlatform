from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionRoutingPolicy:
    minimum_orders_per_route: int = 2
    minimum_route_score: float = 50.0
    maximum_shortfall_bps: float = 50.0
    minimum_fill_ratio: float = 0.80
    maximum_latency_seconds: float = 20.0
    maximum_spread_bps: float = 100.0
    reject_unqualified_routes: bool = False
    shortfall_weight: float = 0.35
    fill_weight: float = 0.20
    latency_weight: float = 0.15
    spread_weight: float = 0.15
    consistency_weight: float = 0.15
