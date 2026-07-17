from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

from .observability_policy import MetricsPolicy
from .observability_profile import MetricDefinition, MetricSample


_ALLOWED_TYPES = {"COUNTER", "GAUGE", "HISTOGRAM"}


class MetricsRegistry:
    def __init__(
        self,
        *,
        policy: MetricsPolicy | None = None,
        path: str | Path = (
            "data/observability/metrics_registry.json"
        ),
    ) -> None:
        self.policy = policy or MetricsPolicy()
        self.policy.validate()
        self.path = Path(path)
        self._definitions: dict[str, MetricDefinition] = {}
        self._samples: list[MetricSample] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._definitions = {
            name: MetricDefinition(
                **{
                    **raw,
                    "label_names": tuple(raw.get("label_names", ())),
                }
            )
            for name, raw in payload.get("definitions", {}).items()
        }
        self._samples = [
            MetricSample(**raw)
            for raw in payload.get("samples", [])
        ]

    def _persist(self) -> None:
        if not self.policy.persist_registry:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(
                {
                    "definitions": {
                        name: asdict(value)
                        for name, value in self._definitions.items()
                    },
                    "samples": [
                        asdict(value) for value in self._samples
                    ],
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def register(
        self,
        definition: MetricDefinition,
    ) -> MetricDefinition:
        normalized = definition.metric_type.upper()
        if normalized not in _ALLOWED_TYPES:
            raise ValueError("Unsupported metric type")
        if len(definition.label_names) > self.policy.maximum_label_count:
            raise ValueError("Metric label count exceeds policy")
        existing = self._definitions.get(definition.name)
        if existing and existing != definition:
            raise ValueError(
                f"Metric already registered differently: {definition.name}"
            )
        self._definitions[definition.name] = definition
        self._persist()
        return definition

    def record(
        self,
        *,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        exemplar_trace_id: str | None = None,
        exemplar_span_id: str | None = None,
    ) -> MetricSample:
        definition = self._definitions.get(name)
        if definition is None:
            if not self.policy.allow_dynamic_metric_registration:
                raise KeyError(f"Metric is not registered: {name}")
            definition = self.register(
                MetricDefinition(
                    name=name,
                    metric_type="GAUGE",
                    description="Dynamically registered metric.",
                )
            )
        numeric = float(value)
        if self.policy.reject_invalid_values and not math.isfinite(numeric):
            raise ValueError("Metric value must be finite")
        labels = labels or {}
        if set(labels) != set(definition.label_names):
            raise ValueError(
                f"Metric labels must exactly match {definition.label_names}"
            )
        if any(
            len(str(item)) > self.policy.maximum_label_value_length
            for item in labels.values()
        ):
            raise ValueError("Metric label value exceeds policy")
        unique_series = {
            (sample.name, tuple(sorted(sample.labels.items())))
            for sample in self._samples
        }
        prospective = (name, tuple(sorted(labels.items())))
        if (
            prospective not in unique_series
            and len(unique_series) >= self.policy.maximum_unique_series
        ):
            raise RuntimeError("Metric series cardinality limit reached")
        sample = MetricSample(
            name=name,
            metric_type=definition.metric_type,
            value=numeric,
            labels={key: str(value) for key, value in labels.items()},
            exemplar_trace_id=exemplar_trace_id,
            exemplar_span_id=exemplar_span_id,
        )
        self._samples.append(sample)
        self._persist()
        return sample

    def definitions(self) -> tuple[MetricDefinition, ...]:
        return tuple(self._definitions.values())

    def samples(self, name: str | None = None) -> tuple[MetricSample, ...]:
        if name is None:
            return tuple(self._samples)
        return tuple(
            sample for sample in self._samples
            if sample.name == name
        )
