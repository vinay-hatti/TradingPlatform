from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderRoutingPolicy:
    require_validated_state_before_routing: bool = True
    require_routed_state_before_submission: bool = True
    require_broker_readiness: bool = True
    require_matching_account_id: bool = True
    require_matching_asset_capability: bool = True
    require_options_capability_for_option_orders: bool = True
    require_live_capability_for_live_orders: bool = True
    default_route: str = "paper"
    allowed_routes: tuple[str, ...] = ("paper", "live")
    allow_route_fallback: bool = False
    persist_every_transition: bool = True
    fail_closed: bool = True
    minimum_routing_score: float = 85.0

    def validate(self) -> None:
        if not self.allowed_routes:
            raise ValueError("allowed_routes cannot be empty")
        if self.default_route not in self.allowed_routes:
            raise ValueError("default_route must be in allowed_routes")
        if not 0.0 <= self.minimum_routing_score <= 100.0:
            raise ValueError("minimum_routing_score must be between 0 and 100")
