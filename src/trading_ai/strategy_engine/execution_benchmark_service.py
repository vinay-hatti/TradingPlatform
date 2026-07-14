from typing import Iterable, Mapping

from .execution_analytics_profile import ExecutionFill
from .execution_benchmark_engine import ExecutionBenchmarkEngine
from .execution_benchmark_policy import ExecutionBenchmarkPolicy
from .execution_benchmark_profile import ExecutionBenchmarkProfile


class ExecutionBenchmarkService:
    def __init__(self, policy: ExecutionBenchmarkPolicy | None = None, engine: ExecutionBenchmarkEngine | None = None) -> None:
        self.engine = engine or ExecutionBenchmarkEngine(policy=policy)

    def analyze(self, fills: Iterable[ExecutionFill], *, vwap_by_order: Mapping[str, float] | None = None) -> ExecutionBenchmarkProfile:
        return self.engine.analyze(fills, vwap_by_order=vwap_by_order)
