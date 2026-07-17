from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .observability_profile import MetricSample
from .slo_policy import SLOPolicy
from .slo_profile import SLODefinition, SLOEvaluation


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SLOEngine:
    def __init__(self, policy: SLOPolicy | None = None) -> None:
        self.policy = policy or SLOPolicy()
        self.policy.validate()

    def evaluate(
        self,
        definition: SLODefinition,
        samples: Iterable[MetricSample],
        *,
        as_of: datetime | None = None,
    ) -> SLOEvaluation:
        now = as_of or datetime.now(timezone.utc)
        relevant = []
        for sample in samples:
            if sample.name != definition.metric_name:
                continue
            if any(
                sample.labels.get(key) != value
                for key, value in definition.labels.items()
            ):
                continue
            if (
                now - _parse(sample.timestamp)
            ).total_seconds() <= definition.window_seconds:
                relevant.append(sample)

        if len(relevant) < self.policy.minimum_sample_count:
            compliant = not self.policy.fail_closed_on_insufficient_data
            return SLOEvaluation(
                slo_id=definition.slo_id,
                service_name=definition.service_name,
                environment=definition.environment,
                indicator_type=definition.indicator_type,
                target=definition.target,
                observed=0.0,
                compliant=compliant,
                sample_count=len(relevant),
                good_events=0,
                total_events=len(relevant),
                window_seconds=definition.window_seconds,
                recommendation=(
                    "INSUFFICIENT_DATA_ALLOW"
                    if compliant else "INSUFFICIENT_DATA_BLOCK"
                ),
            )

        values = [float(sample.value) for sample in relevant]
        if definition.indicator_type.upper() in {
            "AVAILABILITY", "ERROR_RATE"
        }:
            if definition.threshold is None:
                raise ValueError("threshold is required")
            if definition.good_when == "LESS_THAN_OR_EQUAL":
                good = sum(v <= definition.threshold for v in values)
            else:
                good = sum(v >= definition.threshold for v in values)
            observed = good / len(values)
        elif definition.indicator_type.upper() == "LATENCY":
            if definition.threshold is None:
                raise ValueError("threshold is required")
            good = sum(v <= definition.threshold for v in values)
            observed = good / len(values)
        elif definition.indicator_type.upper() == "THROUGHPUT":
            observed = sum(values) / len(values)
            good = len(values) if observed >= definition.target else 0
        else:
            raise ValueError("Unsupported SLO indicator_type")

        compliant = observed >= definition.target
        return SLOEvaluation(
            slo_id=definition.slo_id,
            service_name=definition.service_name,
            environment=definition.environment,
            indicator_type=definition.indicator_type,
            target=definition.target,
            observed=observed,
            compliant=compliant,
            sample_count=len(values),
            good_events=good,
            total_events=len(values),
            window_seconds=definition.window_seconds,
            recommendation="SLO_HEALTHY" if compliant else "SLO_VIOLATED",
        )
