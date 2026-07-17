from __future__ import annotations

import time
from collections.abc import Callable

from .final_readiness_profile import BenchmarkResult


class PerformanceBenchmarkService:
    @staticmethod
    def _compare(
        observed: float,
        threshold: float,
        comparison: str,
    ) -> bool:
        mapping = {
            "LESS_THAN": observed < threshold,
            "LESS_THAN_OR_EQUAL": observed <= threshold,
            "GREATER_THAN": observed > threshold,
            "GREATER_THAN_OR_EQUAL": observed >= threshold,
            "EQUAL": observed == threshold,
        }
        if comparison not in mapping:
            raise ValueError(f"Unsupported comparison: {comparison}")
        return mapping[comparison]

    def run(
        self,
        *,
        benchmark_id: str,
        category: str,
        metric_name: str,
        operation: Callable[[], float],
        threshold_value: float,
        comparison: str,
        notes: str = "",
    ) -> BenchmarkResult:
        started = time.perf_counter()
        observed = float(operation())
        duration = time.perf_counter() - started
        return BenchmarkResult(
            benchmark_id=benchmark_id,
            category=category,
            metric_name=metric_name,
            observed_value=observed,
            threshold_value=threshold_value,
            comparison=comparison,
            passed=self._compare(
                observed,
                threshold_value,
                comparison,
            ),
            duration_seconds=duration,
            notes=notes,
        )
