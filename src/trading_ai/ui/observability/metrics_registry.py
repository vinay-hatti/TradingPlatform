from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock

from trading_ai.ui.models.observability import MetricPoint


class MetricsRegistry:
    _shared: "MetricsRegistry | None" = None

    def __init__(self):
        self._lock = RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    @classmethod
    def shared(cls) -> "MetricsRegistry":
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None):
        return name, tuple(sorted((labels or {}).items()))

    def increment(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += amount

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def snapshot(self) -> list[MetricPoint]:
        with self._lock:
            now = datetime.now(timezone.utc)
            result: list[MetricPoint] = []
            for (name, label_items), value in sorted(self._counters.items()):
                result.append(
                    MetricPoint(
                        name=name,
                        value=value,
                        unit="count",
                        labels=dict(label_items),
                        observed_at=now,
                    )
                )
            for (name, label_items), value in sorted(self._gauges.items()):
                result.append(
                    MetricPoint(
                        name=name,
                        value=value,
                        unit="gauge",
                        labels=dict(label_items),
                        observed_at=now,
                    )
                )
            return result

    def prometheus_text(self) -> str:
        lines = []
        for metric in self.snapshot():
            labels = ""
            if metric.labels:
                rendered = ",".join(
                    f'{key}="{value}"'
                    for key, value in sorted(metric.labels.items())
                )
                labels = f"{{{rendered}}}"
            safe_name = metric.name.replace(".", "_").replace("-", "_")
            lines.append(f"{safe_name}{labels} {metric.value}")
        return "\n".join(lines) + ("\n" if lines else "")
