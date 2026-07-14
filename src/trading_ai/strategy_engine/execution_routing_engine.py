from __future__ import annotations

from .execution_aggregation_profile import ExecutionAggregationProfile, ExecutionVenueProfile
from .execution_routing_policy import ExecutionRoutingPolicy
from .execution_routing_profile import ExecutionRouteRecommendation, ExecutionRoutingProfile


class ExecutionRoutingEngine:
    """Convert historical venue/broker quality into bounded routing recommendations."""

    def __init__(self, policy: ExecutionRoutingPolicy | None = None) -> None:
        self.policy = policy or ExecutionRoutingPolicy()

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"

    @staticmethod
    def _bounded(value: float, limit: float) -> float:
        return max(0.0, min(100.0, 100.0 * (1.0 - abs(value) / max(limit, 1e-9))))

    def _recommendations(self, profiles: tuple[ExecutionVenueProfile, ...], route_type: str) -> tuple[ExecutionRouteRecommendation, ...]:
        recommendations: list[ExecutionRouteRecommendation] = []
        for item in profiles:
            name = item.venue if route_type == "VENUE" else item.broker
            components = (
                self._bounded(item.average_shortfall_bps, self.policy.maximum_shortfall_bps),
                min(100.0, item.average_fill_ratio * 100.0 / max(self.policy.minimum_fill_ratio, 1e-9)),
                self._bounded(item.average_fill_delay_seconds, self.policy.maximum_latency_seconds),
                self._bounded(item.average_effective_spread_bps, self.policy.maximum_spread_bps),
                self._bounded(item.shortfall_volatility_bps, self.policy.maximum_shortfall_bps),
            )
            weights = (
                self.policy.shortfall_weight,
                self.policy.fill_weight,
                self.policy.latency_weight,
                self.policy.spread_weight,
                self.policy.consistency_weight,
            )
            score = sum(value * weight for value, weight in zip(components, weights)) / sum(weights)
            sample_confidence = min(100.0, 100.0 * item.order_count / max(self.policy.minimum_orders_per_route * 3, 1))
            confidence = 0.70 * sample_confidence + 0.30 * score
            warnings: list[str] = []
            if item.order_count < self.policy.minimum_orders_per_route:
                warnings.append("INSUFFICIENT_ROUTE_HISTORY")
            if abs(item.average_shortfall_bps) > self.policy.maximum_shortfall_bps:
                warnings.append("EXCESSIVE_ROUTE_SHORTFALL")
            if item.average_fill_ratio < self.policy.minimum_fill_ratio:
                warnings.append("LOW_ROUTE_FILL_RATIO")
            if item.average_fill_delay_seconds > self.policy.maximum_latency_seconds:
                warnings.append("HIGH_ROUTE_LATENCY")
            if item.average_effective_spread_bps > self.policy.maximum_spread_bps:
                warnings.append("WIDE_ROUTE_SPREAD")
            allowed = score >= self.policy.minimum_route_score and not (
                item.order_count < self.policy.minimum_orders_per_route and self.policy.reject_unqualified_routes
            )
            rejection = ("UNQUALIFIED_EXECUTION_ROUTE",) if not allowed and self.policy.reject_unqualified_routes else ()
            recommendations.append(ExecutionRouteRecommendation(
                route_type=route_type,
                route_name=name,
                order_count=item.order_count,
                route_score=score,
                confidence_score=confidence,
                average_shortfall_bps=item.average_shortfall_bps,
                average_fill_ratio=item.average_fill_ratio,
                average_latency_seconds=item.average_fill_delay_seconds,
                average_spread_bps=item.average_effective_spread_bps,
                shortfall_volatility_bps=item.shortfall_volatility_bps,
                allowed=allowed,
                valid=item.valid,
                warnings=tuple(warnings),
                rejection_reasons=rejection,
                metadata={"source_rank": item.rank},
            ))
        recommendations.sort(key=lambda item: (-int(item.allowed), -item.route_score, -item.confidence_score, abs(item.average_shortfall_bps)))
        return tuple(ExecutionRouteRecommendation(**{**item.__dict__, "rank": index + 1, "recommended": index == 0 and item.allowed}) for index, item in enumerate(recommendations))

    def analyze(self, aggregation_profile: ExecutionAggregationProfile) -> ExecutionRoutingProfile:
        if not aggregation_profile.valid:
            return ExecutionRoutingProfile(valid=False, allowed=not self.policy.reject_unqualified_routes, warnings=("INVALID_EXECUTION_AGGREGATION_PROFILE",))
        venues = self._recommendations(aggregation_profile.venues, "VENUE")
        brokers = self._recommendations(aggregation_profile.brokers, "BROKER")
        best_venue = next((item for item in venues if item.recommended), None)
        best_broker = next((item for item in brokers if item.recommended), None)
        components = [item.route_score for item in (best_venue, best_broker) if item is not None]
        score = sum(components) / len(components) if components else 0.0
        warnings: list[str] = []
        if best_venue is None:
            warnings.append("NO_QUALIFIED_EXECUTION_VENUE")
        if best_broker is None:
            warnings.append("NO_QUALIFIED_EXECUTION_BROKER")
        severity = "LOW" if score >= 75 else "MODERATE" if score >= 60 else "SEVERE" if score >= 40 else "CRITICAL"
        rejection = ("NO_QUALIFIED_EXECUTION_ROUTE",) if not components and self.policy.reject_unqualified_routes else ()
        return ExecutionRoutingProfile(
            recommended_venue=best_venue.route_name if best_venue else "UNAVAILABLE",
            recommended_broker=best_broker.route_name if best_broker else "UNAVAILABLE",
            venue_confidence_score=best_venue.confidence_score if best_venue else 0.0,
            broker_confidence_score=best_broker.confidence_score if best_broker else 0.0,
            routing_score=score,
            routing_grade=self._grade(score),
            routing_severity=severity,
            allowed=not rejection,
            valid=bool(components),
            warnings=tuple(warnings),
            rejection_reasons=rejection,
            venue_recommendations=venues,
            broker_recommendations=brokers,
            metadata={"method": "HISTORICAL_EXECUTION_QUALITY"},
        )
