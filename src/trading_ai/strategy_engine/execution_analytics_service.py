from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .execution_analytics_engine import ExecutionAnalyticsEngine
from .execution_analytics_policy import ExecutionAnalyticsPolicy
from .execution_analytics_profile import ExecutionAnalyticsProfile, ExecutionFill


class ExecutionAnalyticsService:
    def __init__(self, policy: ExecutionAnalyticsPolicy | None = None, engine: ExecutionAnalyticsEngine | None = None) -> None:
        self.engine = engine or ExecutionAnalyticsEngine(policy)

    @staticmethod
    def _fill(value: ExecutionFill | Mapping[str, Any]) -> ExecutionFill:
        if isinstance(value, ExecutionFill):
            return value
        fields = ExecutionFill.__dataclass_fields__
        return ExecutionFill(**{key: value[key] for key in fields if key in value})

    def analyze(self, fills: Iterable[ExecutionFill | Mapping[str, Any]], *, symbol: str = "", strategy: str = "") -> ExecutionAnalyticsProfile:
        return self.engine.analyze((self._fill(item) for item in fills), symbol=symbol, strategy=strategy)

    def estimate(
        self,
        *,
        symbol: str,
        strategy: str,
        side: str,
        quantity: float,
        decision_price: float,
        bid: float,
        ask: float,
        expected_fill_price: float | None = None,
    ) -> ExecutionAnalyticsProfile:
        midpoint = (float(bid) + float(ask)) / 2.0 if bid and ask else float(decision_price)
        fill_price = float(expected_fill_price) if expected_fill_price is not None else midpoint
        fill = ExecutionFill(
            order_id="ESTIMATED",
            symbol=symbol,
            side=side,
            quantity_requested=quantity,
            quantity_filled=quantity,
            decision_price=decision_price,
            arrival_price=midpoint,
            fill_price=fill_price,
            bid=bid,
            ask=ask,
            venue="ESTIMATED",
            metadata={"estimated": True},
        )
        return self.engine.analyze((fill,), symbol=symbol, strategy=strategy)
