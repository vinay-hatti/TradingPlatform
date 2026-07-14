from __future__ import annotations

from collections import defaultdict
from math import isfinite, sqrt
from statistics import median
from typing import Iterable, Mapping

from .execution_analytics_profile import ExecutionFill
from .execution_benchmark_policy import ExecutionBenchmarkPolicy
from .execution_benchmark_profile import (
    ExecutionBenchmarkOrderResult,
    ExecutionBenchmarkProfile,
    ExecutionBenchmarkSummary,
)


class ExecutionBenchmarkEngine:
    """Evaluate fills against decision, arrival, midpoint and VWAP benchmarks."""

    def __init__(self, policy: ExecutionBenchmarkPolicy | None = None) -> None:
        self.policy = policy or ExecutionBenchmarkPolicy()

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
    def _p90(values: list[float]) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        return values[min(len(values) - 1, max(0, int(round(0.90 * (len(values) - 1)))))]

    def _score(self, average_bps: float, volatility_bps: float) -> float:
        average_component = max(0.0, 100.0 * (1.0 - abs(average_bps) / max(self.policy.severe_average_shortfall_bps, 1e-9)))
        consistency_component = max(0.0, 100.0 * (1.0 - volatility_bps / max(self.policy.severe_average_shortfall_bps, 1e-9)))
        return min(100.0, 0.75 * average_component + 0.25 * consistency_component)

    def analyze(
        self,
        fills: Iterable[ExecutionFill],
        *,
        vwap_by_order: Mapping[str, float] | None = None,
    ) -> ExecutionBenchmarkProfile:
        rows = tuple(fills)
        if not rows:
            rejection = ("NO_EXECUTION_FILLS",) if self.policy.reject_invalid_profile else ()
            return ExecutionBenchmarkProfile(valid=False, allowed=not rejection, warnings=("NO_EXECUTION_FILLS",), rejection_reasons=rejection)

        groups: dict[str, list[ExecutionFill]] = defaultdict(list)
        for index, fill in enumerate(rows):
            groups[fill.order_id or f"ORDER_{index + 1:05d}"].append(fill)

        results: list[ExecutionBenchmarkOrderResult] = []
        enabled = {
            "DECISION_PRICE": self.policy.decision_price_enabled,
            "ARRIVAL_PRICE": self.policy.arrival_price_enabled,
            "MIDPOINT": self.policy.midpoint_enabled,
            "VWAP": self.policy.vwap_enabled,
        }
        vwap_by_order = dict(vwap_by_order or {})

        for order_id, order_fills in groups.items():
            filled = sum(self._number(item.quantity_filled) for item in order_fills)
            if filled <= 0:
                continue
            avg_fill = sum(self._number(item.fill_price) * self._number(item.quantity_filled) for item in order_fills) / filled
            side = order_fills[0].side
            sign = self._side_sign(side)
            weighted = lambda attr: sum(self._number(getattr(item, attr)) * self._number(item.quantity_filled) for item in order_fills) / filled
            decision = weighted("decision_price")
            arrival = weighted("arrival_price")
            bid = weighted("bid")
            ask = weighted("ask")
            midpoint = (bid + ask) / 2.0 if bid > 0 and ask > 0 else 0.0
            metadata_vwap = self._number(order_fills[0].metadata.get("vwap", 0.0))
            benchmarks = {
                "DECISION_PRICE": decision,
                "ARRIVAL_PRICE": arrival,
                "MIDPOINT": midpoint,
                "VWAP": self._number(vwap_by_order.get(order_id, metadata_vwap)),
            }
            for name, price in benchmarks.items():
                if not enabled[name] or price <= 0:
                    continue
                shortfall = sign * (avg_fill - price) * filled
                notional = abs(price * filled)
                shortfall_bps = shortfall / notional * 10000.0 if notional else 0.0
                results.append(ExecutionBenchmarkOrderResult(
                    order_id=order_id,
                    symbol=order_fills[0].symbol,
                    side=side,
                    benchmark_name=name,
                    benchmark_price=price,
                    average_fill_price=avg_fill,
                    shortfall=shortfall,
                    shortfall_bps=shortfall_bps,
                    notional=notional,
                    valid=True,
                    metadata={"filled_quantity": filled},
                ))

        grouped: dict[str, list[ExecutionBenchmarkOrderResult]] = defaultdict(list)
        for result in results:
            grouped[result.benchmark_name].append(result)

        summaries: list[ExecutionBenchmarkSummary] = []
        for name, items in grouped.items():
            values = [item.shortfall_bps for item in items]
            notionals = [max(0.0, item.notional) for item in items]
            total = sum(notionals) or float(len(items))
            if sum(notionals) == 0:
                notionals = [1.0] * len(items)
            average = sum(item.shortfall_bps * weight for item, weight in zip(items, notionals)) / total
            variance = sum((value - average) ** 2 for value in values) / len(values)
            volatility = sqrt(variance)
            score = self._score(average, volatility)
            severity = "LOW"
            warnings: list[str] = []
            if abs(average) >= self.policy.critical_average_shortfall_bps:
                severity = "CRITICAL"; warnings.append("CRITICAL_BENCHMARK_SHORTFALL")
            elif abs(average) >= self.policy.severe_average_shortfall_bps:
                severity = "SEVERE"; warnings.append("SEVERE_BENCHMARK_SHORTFALL")
            elif abs(average) >= self.policy.maximum_average_shortfall_bps:
                severity = "MODERATE"; warnings.append("ELEVATED_BENCHMARK_SHORTFALL")
            if len(items) < self.policy.minimum_orders:
                warnings.append("INSUFFICIENT_BENCHMARK_ORDERS")
            if score < self.policy.minimum_benchmark_score:
                warnings.append("LOW_BENCHMARK_SCORE")
            rejection = ("CRITICAL_EXECUTION_BENCHMARK",) if severity == "CRITICAL" and self.policy.reject_critical_benchmark else ()
            summaries.append(ExecutionBenchmarkSummary(
                benchmark_name=name,
                order_count=len(items),
                average_shortfall_bps=average,
                median_shortfall_bps=median(values),
                p90_shortfall_bps=self._p90(values),
                shortfall_volatility_bps=volatility,
                best_shortfall_bps=min(values),
                worst_shortfall_bps=max(values),
                benchmark_score=score,
                benchmark_grade=self._grade(score),
                benchmark_severity=severity,
                allowed=not rejection,
                valid=True,
                warnings=tuple(warnings),
                rejection_reasons=rejection,
            ))

        summaries.sort(key=lambda item: (-item.benchmark_score, abs(item.average_shortfall_bps)))
        valid = bool(summaries)
        warnings = [] if valid else ["NO_VALID_EXECUTION_BENCHMARKS"]
        rejection = tuple(reason for item in summaries for reason in item.rejection_reasons)
        aggregate = sum(item.benchmark_score for item in summaries) / len(summaries) if summaries else 0.0
        severity_order = {"UNKNOWN": 0, "LOW": 1, "MODERATE": 2, "SEVERE": 3, "CRITICAL": 4}
        severity = max((item.benchmark_severity for item in summaries), key=lambda value: severity_order.get(value, 0), default="UNKNOWN")
        return ExecutionBenchmarkProfile(
            order_count=len(groups),
            benchmark_count=len(summaries),
            best_benchmark=summaries[0].benchmark_name if summaries else "UNAVAILABLE",
            worst_benchmark=summaries[-1].benchmark_name if summaries else "UNAVAILABLE",
            aggregate_benchmark_score=aggregate,
            aggregate_benchmark_grade=self._grade(aggregate),
            aggregate_benchmark_severity=severity,
            allowed=not rejection,
            valid=valid,
            warnings=tuple(warnings),
            rejection_reasons=tuple(dict.fromkeys(rejection)),
            order_results=tuple(results),
            summaries=tuple(summaries),
            metadata={"benchmark_method": "SIGNED_NOTIONAL_WEIGHTED_SHORTFALL"},
        )
