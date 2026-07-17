from typing import Any
from .broker_order_policy import BrokerOrderPolicy
from .broker_order_profile import BrokerOrderRequest, BrokerOrderValidationCheck, BrokerOrderValidationProfile

class BrokerOrderValidationEngine:
    def __init__(self, policy=None) -> None:
        self.policy = policy or BrokerOrderPolicy()
        self.policy.validate()
        self._seen_client_order_ids: set[str] = set()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(self, order: BrokerOrderRequest, *, register_client_order_id: bool = False) -> BrokerOrderValidationProfile:
        checks = []
        def add(name: str, passed: bool, message: str, required: bool = True, metadata=None):
            checks.append(BrokerOrderValidationCheck(name, bool(passed), required, 100.0 if passed else 0.0,
                "LOW" if passed else "CRITICAL", message, metadata or {}))
        add("client_order_id", bool(order.client_order_id), "Client order id is required.")
        add("account_id", bool(order.account_id), "Account id is required.")
        add("order_type", order.order_type.upper() in self.policy.allowed_order_types, "Order type is supported.")
        add("time_in_force", order.time_in_force.upper() in self.policy.allowed_time_in_force, "Time in force is supported.")
        add("leg_count", 0 < len(order.legs) <= self.policy.maximum_legs, "Leg count is within policy.", metadata={"leg_count": len(order.legs)})
        add("unique_client_order_id", order.client_order_id not in self._seen_client_order_ids or not self.policy.require_unique_client_order_id, "Client order id is unique.")
        if self.policy.require_limit_price_for_limit_orders and order.order_type.upper() in {"LIMIT", "STOP_LIMIT"}:
            add("limit_price", order.limit_price is not None and order.limit_price > 0, "Limit price is required.")
        if self.policy.require_stop_price_for_stop_orders and order.order_type.upper() in {"STOP", "STOP_LIMIT"}:
            add("stop_price", order.stop_price is not None and order.stop_price > 0, "Stop price is required.")
        if len(order.legs) > 1 and self.policy.reject_market_multi_leg_orders:
            add("multi_leg_market_order", order.order_type.upper() != "MARKET", "Multi-leg market orders are rejected.")
        underlyings = set()
        for leg in order.legs:
            add(f"instrument:{leg.leg_id}", leg.instrument.allowed, "Instrument mapping must be approved.")
            add(f"side:{leg.leg_id}", leg.side.upper() in self.policy.allowed_sides, "Side is supported.")
            add(f"quantity:{leg.leg_id}", self.policy.minimum_quantity <= leg.quantity <= self.policy.maximum_quantity, "Quantity is within policy.")
            add(f"position_effect:{leg.leg_id}", leg.position_effect.upper() in self.policy.allowed_position_effects, "Position effect is supported.")
            add(f"ratio:{leg.leg_id}", leg.ratio > 0, "Leg ratio must be positive.")
            if leg.instrument.option: underlyings.add(leg.instrument.option.underlying_symbol)
            elif leg.instrument.equity: underlyings.add(leg.instrument.equity.symbol)
        if len(order.legs) > 1 and self.policy.require_same_underlying_for_multi_leg:
            add("same_underlying", len(underlyings) <= 1, "Multi-leg order must share an underlying.", metadata={"underlyings": sorted(underlyings)})
        required = [x for x in checks if x.required]
        failed = [x for x in required if not x.passed]
        score = sum(x.score for x in required) / len(required) if required else 100.0
        allowed = not failed and score >= self.policy.minimum_validation_score
        if not self.policy.fail_closed: allowed = score >= self.policy.minimum_validation_score
        grade, severity = self._grade(score)
        if allowed and register_client_order_id: self._seen_client_order_ids.add(order.client_order_id)
        return BrokerOrderValidationProfile(True, allowed, order.client_order_id, round(score, 2), grade, severity,
            "SUBMIT" if allowed else "REJECT", order, tuple(checks), rejection_reasons=tuple(x.name.upper() for x in failed),
            metadata={"leg_count": len(order.legs), "underlyings": sorted(underlyings)})
