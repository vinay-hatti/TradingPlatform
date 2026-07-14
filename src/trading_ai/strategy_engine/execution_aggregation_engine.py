from __future__ import annotations

from collections import defaultdict
from math import isfinite, sqrt
from statistics import median
from typing import Iterable

from .execution_aggregation_policy import ExecutionAggregationPolicy
from .execution_aggregation_profile import (
    ExecutionAggregationProfile,
    ExecutionBenchmarkProfile,
    ExecutionOrderProfile,
    ExecutionVenueProfile,
)
from .execution_analytics_engine import ExecutionAnalyticsEngine
from .execution_analytics_profile import ExecutionFill


class ExecutionAggregationEngine:
    """Aggregate fills to orders, compare venues/brokers and calculate benchmark quality."""

    def __init__(
        self,
        policy: ExecutionAggregationPolicy | None = None,
        analytics_engine: ExecutionAnalyticsEngine | None = None,
    ) -> None:
        self.policy = policy or ExecutionAggregationPolicy()
        self.analytics_engine = analytics_engine or ExecutionAnalyticsEngine()

    @staticmethod
    def _number(value: object, default: float = 0.0) -> float:
        try:
            number = float(value)
            return number if isfinite(number) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _side_sign(side: str) -> float:
        return 1.0 if str(side).upper() in {"BUY", "BOT", "BTO", "BTC"} else -1.0

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"

    @staticmethod
    def _bounded_score(value: float, limit: float) -> float:
        if limit <= 0:
            return 100.0
        return max(0.0, min(100.0, 100.0 * (1.0 - abs(value) / limit)))

    def _order_profiles(self, fills: tuple[ExecutionFill, ...], strategy_by_order: dict[str, str]) -> tuple[ExecutionOrderProfile, ...]:
        groups: dict[str, list[ExecutionFill]] = defaultdict(list)
        for index, fill in enumerate(fills):
            order_id = fill.order_id or f"ORDER_{index + 1:05d}"
            groups[order_id].append(fill)

        out: list[ExecutionOrderProfile] = []
        for order_id, rows in groups.items():
            strategy = strategy_by_order.get(order_id, str(rows[0].metadata.get("strategy", "")))
            profile = self.analytics_engine.analyze(rows, symbol=rows[0].symbol, strategy=strategy)
            venue = str(rows[0].venue or "UNKNOWN")
            broker = str(rows[0].metadata.get("broker", "UNKNOWN"))
            requested = sum(self._number(r.quantity_requested) for r in rows)
            filled = sum(self._number(r.quantity_filled) for r in rows)
            benchmark_price = sum(self._number(r.decision_price) * self._number(r.quantity_filled) for r in rows) / filled if filled else 0.0
            benchmark_cost = sum(
                self._side_sign(r.side) * (self._number(r.fill_price) - benchmark_price) * self._number(r.quantity_filled)
                for r in rows
            )
            notional = abs(benchmark_price * filled)
            benchmark_bps = benchmark_cost / notional * 10000.0 if notional else 0.0
            efficiency = max(0.0, min(100.0, profile.execution_score - max(0.0, benchmark_bps) * 0.10))
            out.append(ExecutionOrderProfile(
                order_id=order_id,
                symbol=rows[0].symbol,
                strategy=strategy,
                venue=venue,
                broker=broker,
                execution_profile=profile,
                benchmark_price=benchmark_price,
                benchmark_name="DECISION_PRICE",
                benchmark_shortfall=benchmark_cost,
                benchmark_shortfall_bps=benchmark_bps,
                execution_efficiency_score=efficiency,
                valid=profile.valid and requested > 0,
                metadata={"requested_quantity": requested, "filled_quantity": filled, "notional": profile.metadata.get("notional", notional)},
            ))
        return tuple(out)

    def _group_profiles(self, orders: tuple[ExecutionOrderProfile, ...], field: str) -> tuple[ExecutionVenueProfile, ...]:
        groups: dict[str, list[ExecutionOrderProfile]] = defaultdict(list)
        for order in orders:
            groups[str(getattr(order, field) or "UNKNOWN")].append(order)
        profiles: list[ExecutionVenueProfile] = []
        for key, rows in groups.items():
            valid = [r for r in rows if r.valid and r.execution_profile]
            if not valid:
                profiles.append(ExecutionVenueProfile(venue=key if field == "venue" else "ALL", broker=key if field == "broker" else "ALL"))
                continue
            weights = [max(0.0, self._number(r.metadata.get("notional", 0.0))) for r in valid]
            total = sum(weights) or float(len(valid))
            if sum(weights) == 0:
                weights = [1.0] * len(valid)
            def wavg(attr: str) -> float:
                return sum(self._number(getattr(r.execution_profile, attr)) * w for r, w in zip(valid, weights)) / total
            shortfalls = [self._number(r.execution_profile.implementation_shortfall_bps) for r in valid]
            mean = sum(shortfalls) / len(shortfalls)
            vol = sqrt(sum((x - mean) ** 2 for x in shortfalls) / len(shortfalls)) if shortfalls else 0.0
            fill_ratio = wavg("fill_ratio")
            delay = wavg("fill_delay_seconds")
            spread = wavg("effective_spread_bps")
            score_components = [
                self._bounded_score(mean, self.policy.severe_average_shortfall_bps),
                max(0.0, min(100.0, fill_ratio * 100.0 / max(self.policy.minimum_average_fill_ratio, 1e-9))),
                self._bounded_score(delay, self.policy.maximum_average_delay_seconds * 2.0),
                self._bounded_score(spread, self.policy.maximum_average_spread_bps * 2.0),
                self._bounded_score(vol, self.policy.severe_average_shortfall_bps),
            ]
            weights_score = [self.policy.shortfall_weight, self.policy.fill_weight, self.policy.latency_weight, self.policy.spread_weight, self.policy.consistency_weight]
            score = sum(a*b for a,b in zip(score_components, weights_score)) / sum(weights_score)
            warnings: list[str] = []
            severity = "LOW"
            if abs(mean) >= self.policy.critical_average_shortfall_bps:
                severity = "CRITICAL"; warnings.append("CRITICAL_GROUP_SHORTFALL")
            elif abs(mean) >= self.policy.severe_average_shortfall_bps:
                severity = "SEVERE"; warnings.append("SEVERE_GROUP_SHORTFALL")
            elif abs(mean) >= self.policy.maximum_average_shortfall_bps:
                severity = "MODERATE"; warnings.append("ELEVATED_GROUP_SHORTFALL")
            if fill_ratio < self.policy.minimum_average_fill_ratio:
                warnings.append("LOW_GROUP_FILL_RATIO")
            if delay > self.policy.maximum_average_delay_seconds:
                warnings.append("HIGH_GROUP_LATENCY")
            rejections = ("CRITICAL_GROUP_EXECUTION",) if severity == "CRITICAL" and self.policy.reject_critical_execution else ()
            profiles.append(ExecutionVenueProfile(
                venue=key if field == "venue" else "ALL",
                broker=key if field == "broker" else "ALL",
                order_count=len(valid),
                notional=sum(weights),
                average_shortfall_bps=mean,
                average_arrival_slippage_bps=wavg("arrival_slippage_bps"),
                average_market_impact_bps=wavg("market_impact_bps"),
                average_effective_spread_bps=spread,
                average_fill_ratio=fill_ratio,
                average_fill_delay_seconds=delay,
                shortfall_volatility_bps=vol,
                execution_score=score,
                execution_grade=self._grade(score),
                execution_severity=severity,
                allowed=not rejections,
                valid=True,
                warnings=tuple(warnings),
                rejection_reasons=rejections,
                metadata={"group_type": field},
            ))
        profiles.sort(key=lambda x: (-x.execution_score, abs(x.average_shortfall_bps), -x.average_fill_ratio))
        return tuple(ExecutionVenueProfile(**{**p.__dict__, "rank": i + 1}) for i, p in enumerate(profiles))

    def _benchmarks(self, orders: tuple[ExecutionOrderProfile, ...]) -> tuple[ExecutionBenchmarkProfile, ...]:
        values = sorted(o.benchmark_shortfall_bps for o in orders if o.valid)
        if not values:
            return ()
        p90 = values[min(len(values) - 1, max(0, int(round(0.90 * (len(values) - 1)))))]
        avg = sum(values) / len(values)
        score = self._bounded_score(avg, self.policy.severe_average_shortfall_bps)
        return (ExecutionBenchmarkProfile(
            benchmark_name="DECISION_PRICE",
            order_count=len(values),
            average_shortfall_bps=avg,
            median_shortfall_bps=median(values),
            p90_shortfall_bps=p90,
            best_shortfall_bps=min(values),
            worst_shortfall_bps=max(values),
            benchmark_score=score,
            benchmark_grade=self._grade(score),
            valid=True,
        ),)

    def analyze(
        self,
        fills: Iterable[ExecutionFill],
        *,
        strategy_by_order: dict[str, str] | None = None,
    ) -> ExecutionAggregationProfile:
        rows = tuple(fills)
        if not rows:
            reasons = ("NO_EXECUTION_FILLS",) if self.policy.reject_invalid_profile else ()
            return ExecutionAggregationProfile(valid=False, allowed=not reasons, warnings=("NO_EXECUTION_FILLS",), rejection_reasons=reasons)
        orders = self._order_profiles(rows, strategy_by_order or {})
        valid_orders = tuple(o for o in orders if o.valid and o.execution_profile)
        if not valid_orders:
            reasons = ("NO_VALID_EXECUTION_ORDERS",) if self.policy.reject_invalid_profile else ()
            return ExecutionAggregationProfile(order_count=len(orders), orders=orders, valid=False, allowed=not reasons, warnings=("NO_VALID_EXECUTION_ORDERS",), rejection_reasons=reasons)
        venues = self._group_profiles(valid_orders, "venue")
        brokers = self._group_profiles(valid_orders, "broker")
        benchmarks = self._benchmarks(valid_orders)
        notionals = [self._number(o.metadata.get("notional", 0.0)) for o in valid_orders]
        total = sum(notionals) or float(len(valid_orders))
        if sum(notionals) == 0:
            notionals = [1.0] * len(valid_orders)
        def order_avg(attr: str) -> float:
            return sum(self._number(getattr(o.execution_profile, attr)) * w for o, w in zip(valid_orders, notionals)) / total
        avg_shortfall = order_avg("implementation_shortfall_bps")
        avg_fill = order_avg("fill_ratio")
        avg_delay = order_avg("fill_delay_seconds")
        score = sum(o.execution_efficiency_score * w for o, w in zip(valid_orders, notionals)) / total
        severity = "LOW"
        warnings: list[str] = []
        if abs(avg_shortfall) >= self.policy.critical_average_shortfall_bps:
            severity = "CRITICAL"; warnings.append("CRITICAL_AGGREGATE_SHORTFALL")
        elif abs(avg_shortfall) >= self.policy.severe_average_shortfall_bps:
            severity = "SEVERE"; warnings.append("SEVERE_AGGREGATE_SHORTFALL")
        elif abs(avg_shortfall) >= self.policy.maximum_average_shortfall_bps:
            severity = "MODERATE"; warnings.append("ELEVATED_AGGREGATE_SHORTFALL")
        if len(venues) < self.policy.minimum_venues_for_comparison:
            warnings.append("INSUFFICIENT_VENUES_FOR_COMPARISON")
        if avg_fill < self.policy.minimum_average_fill_ratio:
            warnings.append("LOW_AGGREGATE_FILL_RATIO")
        rejections = ("CRITICAL_AGGREGATE_EXECUTION",) if severity == "CRITICAL" and self.policy.reject_critical_execution else ()
        return ExecutionAggregationProfile(
            order_count=len(valid_orders),
            venue_count=len(venues),
            broker_count=len(brokers),
            total_notional=sum(notionals),
            average_shortfall_bps=avg_shortfall,
            average_fill_ratio=avg_fill,
            average_delay_seconds=avg_delay,
            best_venue=venues[0].venue if venues else "UNAVAILABLE",
            worst_venue=venues[-1].venue if venues else "UNAVAILABLE",
            best_broker=brokers[0].broker if brokers else "UNAVAILABLE",
            worst_broker=brokers[-1].broker if brokers else "UNAVAILABLE",
            aggregate_execution_score=score,
            aggregate_execution_grade=self._grade(score),
            aggregate_execution_severity=severity,
            allowed=not rejections,
            valid=True,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=rejections,
            orders=orders,
            venues=venues,
            brokers=brokers,
            benchmarks=benchmarks,
            metadata={"comparison_method": "NOTIONAL_WEIGHTED"},
        )
