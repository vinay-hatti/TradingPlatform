from typing import Iterable

from .execution_aggregation_engine import ExecutionAggregationEngine
from .execution_aggregation_policy import ExecutionAggregationPolicy
from .execution_aggregation_profile import ExecutionAggregationProfile
from .execution_analytics_profile import ExecutionFill


class ExecutionAggregationService:
    def __init__(self, policy: ExecutionAggregationPolicy | None = None, engine: ExecutionAggregationEngine | None = None) -> None:
        self.engine = engine or ExecutionAggregationEngine(policy=policy)

    def analyze(self, fills: Iterable[ExecutionFill], *, strategy_by_order: dict[str, str] | None = None) -> ExecutionAggregationProfile:
        return self.engine.analyze(fills, strategy_by_order=strategy_by_order)
