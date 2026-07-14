from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .execution_aggregation_service import ExecutionAggregationService
from .execution_benchmark_service import ExecutionBenchmarkService
from .execution_routing_service import ExecutionRoutingService
from .execution_integration_policy import ExecutionIntegrationPolicy
from .execution_integration_profile import ExecutionIntegrationProfile


class ExecutionIntegrationService:
    def __init__(self, policy=None, aggregation_service=None, benchmark_service=None, routing_service=None):
        self.policy = policy or ExecutionIntegrationPolicy()
        self.policy.validate()
        self.aggregation_service = aggregation_service or ExecutionAggregationService()
        self.benchmark_service = benchmark_service or ExecutionBenchmarkService()
        self.routing_service = routing_service or ExecutionRoutingService()

    def analyze(self, fills: Iterable[Any] | None, vwap_by_order=None) -> ExecutionIntegrationProfile:
        fills = list(fills or [])
        if not self.policy.enabled:
            return ExecutionIntegrationProfile(valid=False, allowed=True, warnings=["EXECUTION_INTEGRATION_DISABLED"])
        if not fills:
            allowed = not self.policy.require_valid_execution_profile
            return ExecutionIntegrationProfile(valid=False, allowed=allowed, warnings=["NO_EXECUTION_FILLS"], rejection_reasons=[] if allowed else ["VALID_EXECUTION_PROFILE_REQUIRED"])
        try:
            aggregation = self.aggregation_service.analyze(fills)
            benchmark = self.benchmark_service.analyze(fills, vwap_by_order=vwap_by_order)
            routing, routed_benchmark = self.routing_service.analyze(fills, vwap_by_order=vwap_by_order)
            if not getattr(benchmark, "valid", False) and getattr(routed_benchmark, "valid", False):
                benchmark = routed_benchmark
        except Exception as exc:
            allowed = not self.policy.require_valid_execution_profile
            return ExecutionIntegrationProfile(valid=False, allowed=allowed, warnings=[f"EXECUTION_INTEGRATION_FAILED: {exc}"], rejection_reasons=[] if allowed else ["EXECUTION_INTEGRATION_FAILED"], metadata={"exception_type": type(exc).__name__})

        valid = bool(getattr(aggregation, "valid", False))
        execution_score = float(getattr(aggregation, "aggregate_execution_score", 0.0) or 0.0)
        routing_score = float(getattr(routing, "routing_score", 0.0) or 0.0)
        shortfall = float(getattr(aggregation, "average_shortfall_bps", 0.0) or 0.0)
        severity = str(getattr(aggregation, "aggregate_execution_severity", "UNKNOWN") or "UNKNOWN").upper()
        allowed = bool(getattr(aggregation, "allowed", True)) and bool(getattr(routing, "allowed", True))
        rejections = list(getattr(aggregation, "rejection_reasons", ()) or ()) + list(getattr(routing, "rejection_reasons", ()) or ())
        warnings = list(getattr(aggregation, "warnings", ()) or ()) + list(getattr(benchmark, "warnings", ()) or ()) + list(getattr(routing, "warnings", ()) or ())
        if execution_score < self.policy.minimum_execution_score:
            warnings.append("EXECUTION_SCORE_BELOW_INTEGRATION_MINIMUM")
            if self.policy.reject_unapproved_execution:
                allowed = False; rejections.append("EXECUTION_SCORE_BELOW_INTEGRATION_MINIMUM")
        if routing.valid and routing_score < self.policy.minimum_routing_score:
            warnings.append("ROUTING_SCORE_BELOW_INTEGRATION_MINIMUM")
        if shortfall > self.policy.maximum_shortfall_bps:
            warnings.append("EXECUTION_SHORTFALL_EXCEEDS_INTEGRATION_LIMIT")
            if self.policy.reject_unapproved_execution:
                allowed = False; rejections.append("EXECUTION_SHORTFALL_EXCEEDS_INTEGRATION_LIMIT")
        if severity == "CRITICAL" and self.policy.reject_critical_execution:
            allowed = False; rejections.append("CRITICAL_EXECUTION_QUALITY")
        if not valid and self.policy.require_valid_execution_profile:
            allowed = False; rejections.append("VALID_EXECUTION_PROFILE_REQUIRED")
        return ExecutionIntegrationProfile(
            valid=valid, allowed=allowed, execution_score=execution_score,
            execution_grade=str(getattr(aggregation, "aggregate_execution_grade", "N/A")),
            execution_severity=severity, average_shortfall_bps=shortfall,
            average_fill_ratio=float(getattr(aggregation, "average_fill_ratio", 0.0) or 0.0),
            average_latency_seconds=float(getattr(aggregation, "average_delay_seconds", 0.0) or 0.0),
            benchmark_score=float(getattr(benchmark, "aggregate_benchmark_score", 0.0) or 0.0),
            benchmark_grade=str(getattr(benchmark, "aggregate_benchmark_grade", "N/A")),
            best_benchmark=str(getattr(benchmark, "best_benchmark", "UNAVAILABLE")),
            recommended_venue=str(getattr(routing, "recommended_venue", "UNAVAILABLE")),
            recommended_broker=str(getattr(routing, "recommended_broker", "UNAVAILABLE")),
            routing_score=routing_score, routing_grade=str(getattr(routing, "routing_grade", "N/A")),
            routing_severity=str(getattr(routing, "routing_severity", "UNKNOWN")),
            order_count=int(getattr(aggregation, "order_count", 0) or 0),
            venue_count=int(getattr(aggregation, "venue_count", 0) or 0), broker_count=int(getattr(aggregation, "broker_count", 0) or 0),
            aggregation_profile=aggregation, benchmark_profile=benchmark, routing_profile=routing,
            warnings=list(dict.fromkeys(warnings)), rejection_reasons=list(dict.fromkeys(rejections)),
            metadata={"source": "PHASE9_EXECUTION_INTEGRATION"},
        )

    def attach(self, decisions, profile: ExecutionIntegrationProfile):
        orders_by_symbol = defaultdict(list)
        aggregation = profile.aggregation_profile
        for order in getattr(aggregation, "orders", ()) or ():
            orders_by_symbol[str(getattr(order, "symbol", "") or "").upper()].append(order)
        for decision in decisions or []:
            symbol = str(getattr(decision, "symbol", "") or "").upper()
            orders = orders_by_symbol.get(symbol, [])
            symbol_shortfall = profile.average_shortfall_bps
            symbol_score = profile.execution_score
            if orders:
                valid_orders = [o for o in orders if getattr(o, "valid", False)]
                if valid_orders:
                    symbol_shortfall = sum(float(getattr(o, "benchmark_shortfall_bps", 0.0) or 0.0) for o in valid_orders) / len(valid_orders)
                    symbol_score = sum(float(getattr(o, "execution_efficiency_score", 0.0) or 0.0) for o in valid_orders) / len(valid_orders)
            decision.execution_analytics_valid = profile.valid
            decision.execution_analytics_allowed = profile.allowed
            decision.execution_analytics_score = round(symbol_score, 4)
            decision.execution_analytics_grade = profile.execution_grade
            decision.execution_analytics_severity = profile.execution_severity
            decision.execution_shortfall_bps = round(symbol_shortfall, 4)
            decision.execution_fill_ratio = round(profile.average_fill_ratio, 6)
            decision.execution_latency_seconds = round(profile.average_latency_seconds, 4)
            decision.execution_benchmark_score = round(profile.benchmark_score, 4)
            decision.execution_best_benchmark = profile.best_benchmark
            decision.recommended_execution_venue = profile.recommended_venue
            decision.recommended_execution_broker = profile.recommended_broker
            decision.execution_routing_score = round(profile.routing_score, 4)
            decision.execution_integration_profile = profile
            decision.metadata["execution_integration_profile"] = profile
            decision.warnings.extend(x for x in profile.warnings if x not in decision.warnings)
            if not profile.allowed:
                decision.rejection_reasons.extend(x for x in profile.rejection_reasons if x not in decision.rejection_reasons)
                decision.allowed = False
        return decisions
