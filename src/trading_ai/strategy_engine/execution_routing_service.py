from typing import Iterable, Mapping

from .execution_aggregation_service import ExecutionAggregationService
from .execution_analytics_profile import ExecutionFill
from .execution_benchmark_profile import ExecutionBenchmarkProfile
from .execution_benchmark_service import ExecutionBenchmarkService
from .execution_routing_engine import ExecutionRoutingEngine
from .execution_routing_policy import ExecutionRoutingPolicy
from .execution_routing_profile import ExecutionRoutingProfile


class ExecutionRoutingService:
    def __init__(
        self,
        policy: ExecutionRoutingPolicy | None = None,
        engine: ExecutionRoutingEngine | None = None,
        aggregation_service: ExecutionAggregationService | None = None,
        benchmark_service: ExecutionBenchmarkService | None = None,
    ) -> None:
        self.engine = engine or ExecutionRoutingEngine(policy=policy)
        self.aggregation_service = aggregation_service or ExecutionAggregationService()
        self.benchmark_service = benchmark_service or ExecutionBenchmarkService()

    def analyze(self, fills: Iterable[ExecutionFill], *, vwap_by_order: Mapping[str, float] | None = None) -> tuple[ExecutionRoutingProfile, ExecutionBenchmarkProfile]:
        rows = tuple(fills)
        aggregation = self.aggregation_service.analyze(rows)
        routing = self.engine.analyze(aggregation)
        benchmarks = self.benchmark_service.analyze(rows, vwap_by_order=vwap_by_order)
        return routing, benchmarks
