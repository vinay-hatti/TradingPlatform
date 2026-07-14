from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Iterable

from .execution_analytics_policy import ExecutionAnalyticsPolicy
from .execution_analytics_profile import ExecutionAnalyticsProfile, ExecutionFill


class ExecutionAnalyticsEngine:
    """Measure implementation shortfall, spread capture, impact and fill quality."""

    def __init__(self, policy: ExecutionAnalyticsPolicy | None = None) -> None:
        self.policy = policy or ExecutionAnalyticsPolicy()

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
    def _bounded_score(value: float, threshold: float) -> float:
        if threshold <= 0:
            return 100.0
        return max(0.0, min(100.0, 100.0 * (1.0 - abs(value) / threshold)))

    @staticmethod
    def _delay_seconds(start: object, end: object) -> float:
        if not start or not end:
            return 0.0
        try:
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return max(0.0, float((end - start).total_seconds()))
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def analyze(
        self,
        fills: Iterable[ExecutionFill],
        *,
        symbol: str = "",
        strategy: str = "",
    ) -> ExecutionAnalyticsProfile:
        rows = tuple(fills)
        if not rows:
            reasons = ("NO_EXECUTION_FILLS",) if self.policy.reject_invalid_profile else ()
            return ExecutionAnalyticsProfile(
                symbol=symbol,
                strategy=strategy,
                allowed=not reasons,
                valid=False,
                warnings=("NO_EXECUTION_FILLS",),
                rejection_reasons=reasons,
            )

        requested = sum(max(0.0, self._number(r.quantity_requested)) for r in rows)
        filled = sum(max(0.0, self._number(r.quantity_filled)) for r in rows)
        valid_rows = tuple(r for r in rows if self._number(r.quantity_filled) > 0 and self._number(r.fill_price) > 0)
        if not valid_rows or requested <= 0:
            reasons = ("INVALID_EXECUTION_FILL_DATA",) if self.policy.reject_invalid_profile else ()
            return ExecutionAnalyticsProfile(
                symbol=symbol or rows[0].symbol,
                strategy=strategy,
                order_count=len(rows),
                requested_quantity=requested,
                filled_quantity=filled,
                fill_ratio=(filled / requested if requested else 0.0),
                allowed=not reasons,
                valid=False,
                warnings=("INVALID_EXECUTION_FILL_DATA",),
                rejection_reasons=reasons,
                fills=rows,
            )

        total_weight = sum(self._number(r.quantity_filled) for r in valid_rows)
        weighted = lambda field: sum(self._number(getattr(r, field)) * self._number(r.quantity_filled) for r in valid_rows) / total_weight
        decision = weighted("decision_price")
        arrival = weighted("arrival_price") or decision
        fill = weighted("fill_price")
        bid = weighted("bid")
        ask = weighted("ask")
        midpoint = (bid + ask) / 2.0 if bid > 0 and ask > 0 else arrival
        spread = max(0.0, ask - bid) if ask > 0 and bid > 0 else 0.0
        spread_pct = spread / midpoint if midpoint > 0 else 0.0

        signed_fill_cost = sum(
            self._side_sign(r.side) * (self._number(r.fill_price) - self._number(r.decision_price or decision))
            * self._number(r.quantity_filled)
            for r in valid_rows
        )
        signed_arrival_cost = sum(
            self._side_sign(r.side) * (self._number(r.fill_price) - self._number(r.arrival_price or arrival))
            * self._number(r.quantity_filled)
            for r in valid_rows
        )
        impact = sum(
            self._side_sign(r.side) * (self._number(r.fill_price) - midpoint)
            * self._number(r.quantity_filled)
            for r in valid_rows
        )
        timing = signed_fill_cost - signed_arrival_cost
        notional = sum(abs(self._number(r.decision_price or decision) * self._number(r.quantity_filled)) for r in valid_rows)
        bps = lambda value: (value / notional * 10000.0) if notional > 0 else 0.0
        effective_spread = 2.0 * abs(impact) / total_weight if total_weight else 0.0
        effective_spread_bps = (effective_spread / midpoint * 10000.0) if midpoint > 0 else 0.0
        fill_ratio = min(1.0, filled / requested) if requested else 0.0
        delay = sum(self._delay_seconds(r.submitted_at, r.filled_at) * self._number(r.quantity_filled) for r in valid_rows) / total_weight

        shortfall_bps = bps(signed_fill_cost)
        arrival_bps = bps(signed_arrival_cost)
        impact_bps = bps(impact)
        timing_bps = bps(timing)

        slippage_score = self._bounded_score(shortfall_bps, self.policy.severe_slippage_bps)
        spread_score = self._bounded_score(spread_pct, self.policy.severe_spread_pct)
        impact_score = self._bounded_score(impact_bps, self.policy.maximum_market_impact_bps * 2.0)
        fill_score = max(0.0, min(100.0, 100.0 * fill_ratio / max(self.policy.minimum_fill_ratio, 1e-9)))
        latency_score = self._bounded_score(delay, self.policy.maximum_fill_delay_seconds * 2.0)
        weight_total = (
            self.policy.slippage_weight + self.policy.spread_weight + self.policy.impact_weight
            + self.policy.fill_weight + self.policy.latency_weight
        )
        score = (
            slippage_score * self.policy.slippage_weight
            + spread_score * self.policy.spread_weight
            + impact_score * self.policy.impact_weight
            + fill_score * self.policy.fill_weight
            + latency_score * self.policy.latency_weight
        ) / weight_total

        warnings: list[str] = []
        rejections: list[str] = []
        severity = "LOW"
        if abs(shortfall_bps) >= self.policy.critical_slippage_bps:
            severity = "CRITICAL"
            warnings.append("CRITICAL_EXECUTION_SLIPPAGE")
        elif abs(shortfall_bps) >= self.policy.severe_slippage_bps or spread_pct >= self.policy.severe_spread_pct:
            severity = "SEVERE"
            warnings.append("SEVERE_EXECUTION_COST")
        elif abs(shortfall_bps) >= self.policy.maximum_slippage_bps or spread_pct >= self.policy.maximum_spread_pct:
            severity = "MODERATE"
            warnings.append("ELEVATED_EXECUTION_COST")
        if abs(impact_bps) > self.policy.maximum_market_impact_bps:
            warnings.append("EXCESSIVE_MARKET_IMPACT")
        if fill_ratio < self.policy.minimum_fill_ratio:
            warnings.append("LOW_FILL_RATIO")
        if delay > self.policy.maximum_fill_delay_seconds:
            warnings.append("EXCESSIVE_FILL_DELAY")
        if score < self.policy.minimum_execution_score:
            warnings.append("LOW_EXECUTION_SCORE")
        if severity == "CRITICAL" and self.policy.reject_critical_execution:
            rejections.append("CRITICAL_EXECUTION_RISK")

        grade = "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"
        return ExecutionAnalyticsProfile(
            symbol=symbol or valid_rows[0].symbol,
            strategy=strategy,
            order_count=len(rows),
            requested_quantity=requested,
            filled_quantity=filled,
            fill_ratio=fill_ratio,
            decision_price=decision,
            arrival_price=arrival,
            average_fill_price=fill,
            average_bid=bid,
            average_ask=ask,
            quoted_spread=spread,
            quoted_spread_pct=spread_pct,
            effective_spread=effective_spread,
            effective_spread_bps=effective_spread_bps,
            implementation_shortfall=signed_fill_cost,
            implementation_shortfall_bps=shortfall_bps,
            arrival_slippage=signed_arrival_cost,
            arrival_slippage_bps=arrival_bps,
            market_impact=impact,
            market_impact_bps=impact_bps,
            timing_cost=timing,
            timing_cost_bps=timing_bps,
            total_commission=sum(self._number(r.commission) for r in rows),
            total_fees=sum(self._number(r.fees) for r in rows),
            fill_delay_seconds=delay,
            slippage_score=slippage_score,
            spread_score=spread_score,
            impact_score=impact_score,
            fill_quality_score=fill_score,
            latency_score=latency_score,
            execution_score=score,
            execution_grade=grade,
            execution_severity=severity,
            allowed=not rejections,
            valid=True,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            fills=rows,
            metadata={"notional": notional, "midpoint": midpoint},
        )
