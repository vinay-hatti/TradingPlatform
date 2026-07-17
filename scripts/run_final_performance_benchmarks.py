from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import time

from trading_ai.deployment.performance_benchmark_service import (
    PerformanceBenchmarkService,
)


def main() -> None:
    service = PerformanceBenchmarkService()

    results = (
        service.run(
            benchmark_id="readiness-engine-throughput",
            category="PERFORMANCE",
            metric_name="operations_per_second",
            operation=lambda: _throughput(),
            threshold_value=10000.0,
            comparison="GREATER_THAN_OR_EQUAL",
            notes="Synthetic governance evaluation benchmark.",
        ),
        service.run(
            benchmark_id="report-build-latency",
            category="PERFORMANCE",
            metric_name="seconds",
            operation=lambda: _latency(),
            threshold_value=1.0,
            comparison="LESS_THAN_OR_EQUAL",
            notes="Synthetic final-report build latency.",
        ),
    )

    path = Path("reports/final_performance_benchmarks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"benchmarks": [asdict(item) for item in results]},
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"Final performance benchmarks written: {path}")


def _throughput() -> float:
    started = time.perf_counter()
    count = 20000
    total = 0
    for value in range(count):
        total += value
    elapsed = max(time.perf_counter() - started, 1e-9)
    return count / elapsed


def _latency() -> float:
    started = time.perf_counter()
    payload = {"status": "ready", "checks": list(range(1000))}
    _ = json.dumps(payload)
    return time.perf_counter() - started


if __name__ == "__main__":
    main()
