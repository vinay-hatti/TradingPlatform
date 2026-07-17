from __future__ import annotations

import re
from typing import Iterable

from .export_policy import PrometheusExpositionPolicy
from .export_profile import AggregatedMetric
from .observability_profile import MetricDefinition


_INVALID = re.compile(r"[^a-zA-Z0-9_:]")


def _metric_name(value: str) -> str:
    cleaned = _INVALID.sub("_", value)
    if not cleaned:
        raise ValueError("Metric name cannot be empty")
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def _escape_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    body = ",".join(
        f'{_metric_name(key)}="{_escape_label(str(value))}"'
        for key, value in sorted(labels.items())
    )
    return "{" + body + "}"


class PrometheusExpositionService:
    def __init__(
        self,
        policy: PrometheusExpositionPolicy | None = None,
    ) -> None:
        self.policy = policy or PrometheusExpositionPolicy()
        self.policy.validate()

    def render(
        self,
        *,
        definitions: Iterable[MetricDefinition],
        metrics: Iterable[AggregatedMetric],
    ) -> str:
        definitions_by_name = {
            item.name: item for item in definitions
        }
        lines = []
        emitted = set()
        for metric in metrics:
            name = _metric_name(
                self.policy.metric_name_prefix + metric.name
            )
            definition = definitions_by_name.get(metric.name)
            if name not in emitted:
                if self.policy.include_help and definition:
                    help_text = definition.description.replace(
                        "\\", "\\\\"
                    ).replace("\n", "\\n")
                    lines.append(f"# HELP {name} {help_text}")
                if self.policy.include_type:
                    kind = {
                        "COUNTER": "counter",
                        "GAUGE": "gauge",
                        "HISTOGRAM": "histogram",
                    }.get(metric.metric_type.upper(), "gauge")
                    lines.append(f"# TYPE {name} {kind}")
                emitted.add(name)

            suffix = (
                f" {metric.updated_at}"
                if self.policy.include_timestamps else ""
            )
            label_text = _labels(metric.labels)
            if metric.metric_type.upper() == "HISTOGRAM":
                for boundary, count in metric.buckets.items():
                    bucket_labels = dict(metric.labels)
                    bucket_labels["le"] = boundary
                    lines.append(
                        f"{name}_bucket{_labels(bucket_labels)} "
                        f"{count}{suffix}"
                    )
                lines.append(
                    f"{name}_sum{label_text} "
                    f"{metric.sum_value or 0.0}{suffix}"
                )
                lines.append(
                    f"{name}_count{label_text} "
                    f"{metric.sample_count}{suffix}"
                )
            else:
                lines.append(
                    f"{name}{label_text} "
                    f"{metric.value or 0.0}{suffix}"
                )
        if self.policy.openmetrics_eof:
            lines.append("# EOF")
        return "\n".join(lines) + "\n"
