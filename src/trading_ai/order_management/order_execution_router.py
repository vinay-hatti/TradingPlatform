from __future__ import annotations

from typing import Iterable

from .order_policy import OrderLifecyclePolicy
from .order_profile import CanonicalOrderAggregate
from .order_routing_policy import OrderRoutingPolicy
from .order_routing_profile import (
    OrderRouteCandidate,
    OrderRoutingCheck,
    OrderRoutingDecision,
)


class OrderExecutionRouter:
    """Select an eligible broker route for a canonical order aggregate."""

    def __init__(
        self,
        candidates: Iterable[OrderRouteCandidate],
        policy: OrderRoutingPolicy | None = None,
    ) -> None:
        self.policy = policy or OrderRoutingPolicy()
        self.policy.validate()
        self._candidates = tuple(candidates)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def select(
        self,
        aggregate: CanonicalOrderAggregate,
        *,
        requested_route: str | None = None,
    ) -> OrderRoutingDecision:
        route_name = (requested_route or self.policy.default_route).strip().lower()
        candidates = sorted(
            (
                candidate for candidate in self._candidates
                if candidate.enabled and candidate.route_id == route_name
            ),
            key=lambda item: item.priority,
        )

        warnings: list[str] = []
        if not candidates and self.policy.allow_route_fallback:
            candidates = sorted(
                (candidate for candidate in self._candidates if candidate.enabled),
                key=lambda item: item.priority,
            )
            warnings.append("ROUTE_FALLBACK_USED")

        candidate = candidates[0] if candidates else None
        checks: list[OrderRoutingCheck] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict | None = None,
        ) -> None:
            checks.append(
                OrderRoutingCheck(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add("route_allowed", route_name in self.policy.allowed_routes, "Requested route is allowed.")
        add("route_available", candidate is not None, "Requested route is available.")

        if candidate is not None:
            add(
                "account_match",
                candidate.account_id == aggregate.account_id
                or not self.policy.require_matching_account_id,
                "Route account matches canonical order account.",
            )
            asset_classes = {leg.asset_class.upper() for leg in aggregate.legs}
            requires_options = "OPTION" in asset_classes
            requires_equities = "EQUITY" in asset_classes

            add(
                "equity_capability",
                not requires_equities or candidate.supports_equities,
                "Route supports equity instruments.",
                required=self.policy.require_matching_asset_capability,
            )
            add(
                "options_capability",
                not requires_options or candidate.supports_options,
                "Route supports option instruments.",
                required=self.policy.require_options_capability_for_option_orders,
            )
            add(
                "multi_leg_capability",
                len(aggregate.legs) <= 1
                or not requires_options
                or candidate.supports_multi_leg_options,
                "Route supports multi-leg option orders.",
            )
            live_requested = candidate.environment.lower() == "production"
            add(
                "live_capability",
                not live_requested or candidate.supports_live_trading,
                "Route supports live trading.",
                required=self.policy.require_live_capability_for_live_orders,
            )

        required = [check for check in checks if check.required]
        failed = [check for check in required if not check.passed]
        score = (
            sum(check.score for check in required) / len(required)
            if required else 100.0
        )
        allowed = (
            candidate is not None
            and not failed
            and score >= self.policy.minimum_routing_score
        )
        if not self.policy.fail_closed:
            allowed = candidate is not None

        grade, severity = self._grade(score)
        return OrderRoutingDecision(
            valid=True,
            allowed=allowed,
            aggregate_id=aggregate.aggregate_id,
            route_id=candidate.route_id if candidate else None,
            broker=candidate.broker if candidate else None,
            account_id=aggregate.account_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="ROUTE" if allowed else "REJECT",
            checks=tuple(checks),
            warnings=tuple(warnings),
            rejection_reasons=tuple(check.name.upper() for check in failed),
            metadata={
                "requested_route": route_name,
                "candidate_environment": candidate.environment if candidate else None,
            },
        )
