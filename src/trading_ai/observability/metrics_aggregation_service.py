from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .export_policy import MetricsAggregationPolicy
from .export_profile import AggregatedMetric
from .observability_profile import MetricDefinition, MetricSample


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MetricsAggregationService:
    def __init__(
        self,
        policy: MetricsAggregationPolicy | None = None,
    ) -> None:
        self.policy = policy or MetricsAggregationPolicy()
        self.policy.validate()

    def aggregate(
        self,
        *,
        definitions: Iterable[MetricDefinition],
        samples: Iterable[MetricSample],
        as_of: datetime | None = None,
    ) -> tuple[AggregatedMetric, ...]:
        now = as_of or datetime.now(timezone.utc)
        definitions_by_name = {
            item.name: item for item in definitions
        }
        groups: dict[
            tuple[str, tuple[tuple[str, str], ...]],
            list[MetricSample],
        ] = defaultdict(list)

        for sample in samples:
            age = (now - _parse(sample.timestamp)).total_seconds()
            if age > self.policy.retention_seconds:
                continue
            key = (
                sample.name,
                tuple(sorted(sample.labels.items())),
            )
            groups[key].append(sample)

        aggregated = []
        for (name, label_items), values in groups.items():
            values = values[-self.policy.maximum_samples_per_series:]
            definition = definitions_by_name.get(name)
            metric_type = (
                definition.metric_type if definition
                else values[-1].metric_type
            ).upper()
            numeric = [float(item.value) for item in values]
            latest = values[-1]
            common = {
                "name": name,
                "metric_type": metric_type,
                "labels": dict(label_items),
                "sample_count": len(values),
                "created_at": (
                    definition.created_at if definition else None
                ),
                "updated_at": latest.timestamp,
                "exemplar_trace_id": latest.exemplar_trace_id,
                "exemplar_span_id": latest.exemplar_span_id,
            }
            if metric_type == "COUNTER":
                aggregated.append(
                    AggregatedMetric(
                        **common,
                        value=sum(numeric),
                        sum_value=sum(numeric),
                        min_value=min(numeric),
                        max_value=max(numeric),
                    )
                )
            elif metric_type == "HISTOGRAM":
                buckets = {}
                for boundary in self.policy.histogram_boundaries:
                    buckets[str(boundary)] = sum(
                        value <= boundary for value in numeric
                    )
                buckets["+Inf"] = len(numeric)
                aggregated.append(
                    AggregatedMetric(
                        **common,
                        value=numeric[-1],
                        sum_value=sum(numeric),
                        min_value=min(numeric),
                        max_value=max(numeric),
                        buckets=buckets,
                    )
                )
            else:
                aggregated.append(
                    AggregatedMetric(
                        **common,
                        value=numeric[-1],
                        sum_value=sum(numeric),
                        min_value=min(numeric),
                        max_value=max(numeric),
                    )
                )
        return tuple(sorted(
            aggregated,
            key=lambda item: (
                item.name,
                tuple(sorted(item.labels.items())),
            ),
        ))
