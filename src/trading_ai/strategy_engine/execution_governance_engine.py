from __future__ import annotations

from collections import defaultdict
from math import isfinite, log, sqrt
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping, Sequence

from .execution_governance_policy import ExecutionGovernancePolicy
from .execution_governance_profile import (
    ExecutionGovernanceProfile,
    ExecutionMetricDriftProfile,
    ExecutionPopulationProfile,
    ExecutionSegmentDriftProfile,
)


class ExecutionGovernanceEngine:
    """Detect distribution and performance drift in execution populations."""

    DEFAULT_METRICS = (
        "implementation_shortfall_bps",
        "arrival_slippage_bps",
        "market_impact_bps",
        "effective_spread_bps",
        "fill_ratio",
        "fill_delay_seconds",
        "execution_score",
    )

    SEGMENT_ALIASES = {
        "VENUE": ("venue",),
        "BROKER": ("broker",),
    }

    def __init__(self, policy: ExecutionGovernancePolicy | None = None):
        self.policy = policy or ExecutionGovernancePolicy()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, Mapping):
            if name in obj:
                return obj.get(name, default)
            metadata = obj.get("metadata", {}) or {}
            if isinstance(metadata, Mapping) and name in metadata:
                return metadata.get(name, default)
            return default
        value = getattr(obj, name, None)
        if value is not None:
            return value
        metadata = getattr(obj, "metadata", {}) or {}
        if isinstance(metadata, Mapping):
            return metadata.get(name, default)
        return default

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90.0:
            return "A"
        if score >= 80.0:
            return "B"
        if score >= 70.0:
            return "C"
        if score >= 60.0:
            return "D"
        return "F"

    def _severity(self, psi: float, standardized_shift: float = 0.0) -> str:
        p = self.policy
        magnitude = abs(standardized_shift)
        if psi >= p.critical_psi_threshold or magnitude >= p.critical_standardized_shift:
            return "CRITICAL"
        if psi >= p.severe_psi_threshold or magnitude >= p.severe_standardized_shift:
            return "SEVERE"
        if psi >= p.moderate_psi_threshold or magnitude >= p.moderate_standardized_shift:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def _worst_severity(values: Iterable[str]) -> str:
        rank = {"UNKNOWN": 0, "LOW": 1, "MODERATE": 2, "SEVERE": 3, "CRITICAL": 4}
        return max(values, key=lambda item: rank.get(str(item).upper(), 0), default="UNKNOWN")

    def _extract(self, rows: Sequence[Any], metric: str) -> list[float]:
        values: list[float] = []
        aliases = {
            "fill_delay_seconds": ("fill_delay_seconds", "average_fill_delay_seconds", "average_latency_seconds"),
            "execution_score": ("execution_score", "aggregate_execution_score"),
            "implementation_shortfall_bps": ("implementation_shortfall_bps", "average_shortfall_bps"),
            "arrival_slippage_bps": ("arrival_slippage_bps", "average_arrival_slippage_bps"),
            "market_impact_bps": ("market_impact_bps", "average_market_impact_bps"),
            "effective_spread_bps": ("effective_spread_bps", "average_effective_spread_bps", "average_spread_bps"),
            "fill_ratio": ("fill_ratio", "average_fill_ratio"),
        }
        for row in rows:
            raw = None
            for candidate in aliases.get(metric, (metric,)):
                raw = self._value(row, candidate, None)
                if raw is not None:
                    break
            number = self._float(raw)
            if number is not None:
                values.append(number)
        return values

    def _quantile_edges(self, values: Sequence[float], bin_count: int) -> list[float]:
        ordered = sorted(values)
        if not ordered:
            return []
        if len(set(ordered)) == 1:
            value = ordered[0]
            width = max(abs(value) * 0.01, 1.0e-6)
            return [value - width, value + width]
        edges = [ordered[0]]
        count = len(ordered)
        for index in range(1, bin_count):
            position = (count - 1) * index / bin_count
            lower = int(position)
            upper = min(lower + 1, count - 1)
            fraction = position - lower
            edge = ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
            if edge > edges[-1]:
                edges.append(edge)
        if ordered[-1] > edges[-1]:
            edges.append(ordered[-1])
        return edges

    @staticmethod
    def _bin_counts(values: Sequence[float], edges: Sequence[float]) -> list[int]:
        if len(edges) < 2:
            return [len(values)]
        counts = [0 for _ in range(len(edges) - 1)]
        for value in values:
            assigned = False
            for index in range(len(edges) - 1):
                is_last = index == len(edges) - 2
                if edges[index] <= value < edges[index + 1] or (is_last and value <= edges[index + 1]):
                    counts[index] += 1
                    assigned = True
                    break
            if not assigned:
                counts[0 if value < edges[0] else -1] += 1
        return counts

    def population_stability_index(self, baseline: Sequence[float], current: Sequence[float]) -> float:
        if not baseline or not current:
            return 0.0
        edges = self._quantile_edges(baseline, max(2, int(self.policy.psi_bin_count)))
        baseline_counts = self._bin_counts(baseline, edges)
        current_counts = self._bin_counts(current, edges)
        epsilon = max(float(self.policy.psi_epsilon), 1.0e-12)
        baseline_total = max(sum(baseline_counts), 1)
        current_total = max(sum(current_counts), 1)
        psi = 0.0
        for expected_count, actual_count in zip(baseline_counts, current_counts):
            expected = max(expected_count / baseline_total, epsilon)
            actual = max(actual_count / current_total, epsilon)
            psi += (actual - expected) * log(actual / expected)
        return max(0.0, float(psi))

    def _deterioration_limit(self, metric: str) -> tuple[float, bool]:
        p = self.policy
        mapping = {
            "implementation_shortfall_bps": (p.maximum_shortfall_deterioration_bps, True),
            "arrival_slippage_bps": (p.maximum_arrival_slippage_deterioration_bps, True),
            "market_impact_bps": (p.maximum_market_impact_deterioration_bps, True),
            "effective_spread_bps": (p.maximum_effective_spread_deterioration_bps, True),
            "fill_delay_seconds": (p.maximum_latency_deterioration_seconds, True),
            "fill_ratio": (p.maximum_fill_ratio_deterioration, False),
            "execution_score": (p.maximum_execution_score_deterioration, False),
        }
        return mapping.get(metric, (float("inf"), True))

    def analyze_metric(self, metric: str, baseline_values: Sequence[float], current_values: Sequence[float]) -> ExecutionMetricDriftProfile:
        warnings: list[str] = []
        rejections: list[str] = []
        if not baseline_values or not current_values:
            return ExecutionMetricDriftProfile(
                metric_name=metric,
                baseline_observation_count=len(baseline_values),
                current_observation_count=len(current_values),
                valid=False,
                warnings=("INSUFFICIENT_METRIC_OBSERVATIONS",),
            )

        baseline_mean = fmean(baseline_values)
        current_mean = fmean(current_values)
        baseline_std = pstdev(baseline_values) if len(baseline_values) > 1 else 0.0
        current_std = pstdev(current_values) if len(current_values) > 1 else 0.0
        absolute_change = current_mean - baseline_mean
        denominator = max(abs(baseline_mean), self.policy.psi_epsilon)
        relative_change = absolute_change / denominator
        pooled_std = sqrt((baseline_std * baseline_std + current_std * current_std) / 2.0)
        standardized_shift = absolute_change / max(pooled_std, self.policy.psi_epsilon)
        psi = self.population_stability_index(baseline_values, current_values)
        severity = self._severity(psi, standardized_shift)

        limit, higher_is_worse = self._deterioration_limit(metric)
        deterioration = absolute_change if higher_is_worse else -absolute_change
        deteriorated = deterioration > limit
        if deteriorated:
            warnings.append(f"{metric.upper()}_DETERIORATED")

        if severity == "CRITICAL" and self.policy.reject_critical_drift:
            rejections.append(f"CRITICAL_{metric.upper()}_DRIFT")
        elif severity == "SEVERE" and self.policy.reject_severe_drift:
            rejections.append(f"SEVERE_{metric.upper()}_DRIFT")

        psi_penalty = min(60.0, psi / max(self.policy.critical_psi_threshold, self.policy.psi_epsilon) * 60.0)
        shift_penalty = min(30.0, abs(standardized_shift) / max(self.policy.critical_standardized_shift, self.policy.psi_epsilon) * 30.0)
        deterioration_penalty = 10.0 if deteriorated else 0.0
        score = max(0.0, min(100.0, 100.0 - psi_penalty - shift_penalty - deterioration_penalty))
        allowed = not rejections
        return ExecutionMetricDriftProfile(
            metric_name=metric,
            baseline_observation_count=len(baseline_values),
            current_observation_count=len(current_values),
            baseline_mean=baseline_mean,
            current_mean=current_mean,
            absolute_change=absolute_change,
            relative_change=relative_change,
            baseline_standard_deviation=baseline_std,
            current_standard_deviation=current_std,
            standardized_shift=standardized_shift,
            population_stability_index=psi,
            drift_score=score,
            drift_grade=self._grade(score),
            drift_severity=severity,
            deteriorated=deteriorated,
            allowed=allowed,
            valid=True,
            warnings=tuple(warnings),
            rejection_reasons=tuple(rejections),
            metadata={"higher_is_worse": higher_is_worse, "deterioration_limit": limit},
        )

    def _population_profile(self, name: str, rows: Sequence[Any], metrics: Sequence[str], segment_types: Sequence[str]) -> ExecutionPopulationProfile:
        available_metrics = sum(1 for metric in metrics if self._extract(rows, metric))
        segment_names: set[tuple[str, str]] = set()
        for segment_type in segment_types:
            for row in rows:
                segment = self._segment_value(row, segment_type)
                if segment != "UNKNOWN":
                    segment_names.add((segment_type, segment))
        warnings: list[str] = []
        if not rows:
            warnings.append("NO_EXECUTION_OBSERVATIONS")
        return ExecutionPopulationProfile(
            name=name,
            observation_count=len(rows),
            metric_count=available_metrics,
            segment_count=len(segment_names),
            valid=bool(rows and available_metrics),
            warnings=tuple(warnings),
            metadata={"metrics": list(metrics), "segment_types": list(segment_types)},
        )

    def _segment_value(self, row: Any, segment_type: str) -> str:
        aliases = self.SEGMENT_ALIASES.get(segment_type.upper(), (segment_type.lower(),))
        for alias in aliases:
            value = self._value(row, alias, None)
            if value not in (None, ""):
                return str(value).upper()
        return "UNKNOWN"

    def _segment_rows(self, rows: Sequence[Any], segment_type: str) -> dict[str, list[Any]]:
        grouped: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            grouped[self._segment_value(row, segment_type)].append(row)
        return grouped

    def analyze_segment(self, segment_type: str, segment_name: str, baseline_rows: Sequence[Any], current_rows: Sequence[Any], metrics: Sequence[str]) -> ExecutionSegmentDriftProfile:
        warnings: list[str] = []
        if len(baseline_rows) < self.policy.minimum_segment_observations or len(current_rows) < self.policy.minimum_segment_observations:
            warnings.append("INSUFFICIENT_SEGMENT_OBSERVATIONS")
        metric_profiles = tuple(
            profile
            for metric in metrics
            if (profile := self.analyze_metric(metric, self._extract(baseline_rows, metric), self._extract(current_rows, metric))).valid
        )
        if not metric_profiles:
            return ExecutionSegmentDriftProfile(
                segment_type=segment_type,
                segment_name=segment_name,
                baseline_observation_count=len(baseline_rows),
                current_observation_count=len(current_rows),
                valid=False,
                warnings=tuple(warnings + ["NO_VALID_SEGMENT_METRICS"]),
            )
        aggregate_psi = fmean(item.population_stability_index for item in metric_profiles)
        maximum_psi = max(item.population_stability_index for item in metric_profiles)
        score = self._weighted_score(metric_profiles)
        severity = self._worst_severity(item.drift_severity for item in metric_profiles)
        rejections = tuple(reason for item in metric_profiles for reason in item.rejection_reasons)
        return ExecutionSegmentDriftProfile(
            segment_type=segment_type,
            segment_name=segment_name,
            baseline_observation_count=len(baseline_rows),
            current_observation_count=len(current_rows),
            metric_count=len(metric_profiles),
            aggregate_psi=aggregate_psi,
            maximum_psi=maximum_psi,
            drift_score=score,
            drift_grade=self._grade(score),
            drift_severity=severity,
            allowed=not rejections,
            valid=True,
            metric_profiles=metric_profiles,
            warnings=tuple(warnings),
            rejection_reasons=rejections,
            metadata={},
        )

    def _weighted_score(self, profiles: Sequence[ExecutionMetricDriftProfile]) -> float:
        if not profiles:
            return 0.0
        weights = self.policy.metric_weights
        weighted = 0.0
        total = 0.0
        for profile in profiles:
            weight = max(0.0, float(weights.get(profile.metric_name, 1.0)))
            weighted += profile.drift_score * weight
            total += weight
        return weighted / total if total > 0.0 else fmean(item.drift_score for item in profiles)

    def analyze(
        self,
        baseline_observations: Sequence[Any] | Iterable[Any],
        current_observations: Sequence[Any] | Iterable[Any],
        *,
        baseline_name: str = "BASELINE",
        current_name: str = "CURRENT",
        metrics: Sequence[str] | None = None,
        segment_types: Sequence[str] = ("VENUE", "BROKER"),
    ) -> ExecutionGovernanceProfile:
        baseline = list(baseline_observations or [])
        current = list(current_observations or [])
        selected_metrics = tuple(metrics or self.DEFAULT_METRICS)
        selected_segments = tuple(str(value).upper() for value in segment_types)
        warnings: list[str] = []
        rejections: list[str] = []

        baseline_profile = self._population_profile(baseline_name, baseline, selected_metrics, selected_segments)
        current_profile = self._population_profile(current_name, current, selected_metrics, selected_segments)

        if len(baseline) < self.policy.minimum_baseline_observations:
            warnings.append("INSUFFICIENT_BASELINE_OBSERVATIONS")
        if len(current) < self.policy.minimum_current_observations:
            warnings.append("INSUFFICIENT_CURRENT_OBSERVATIONS")
        insufficient = bool(warnings)
        if insufficient and not self.policy.allow_insufficient_data:
            rejections.extend(warnings)

        metric_profiles = tuple(
            profile
            for metric in selected_metrics
            if (profile := self.analyze_metric(metric, self._extract(baseline, metric), self._extract(current, metric))).valid
        )
        if not metric_profiles:
            warnings.append("NO_VALID_EXECUTION_GOVERNANCE_METRICS")
            return ExecutionGovernanceProfile(
                valid=False,
                allowed=self.policy.allow_insufficient_data,
                baseline_name=baseline_name,
                current_name=current_name,
                baseline_observation_count=len(baseline),
                current_observation_count=len(current),
                baseline_profile=baseline_profile,
                current_profile=current_profile,
                warnings=tuple(warnings),
                rejection_reasons=tuple(rejections),
                metadata={"policy": self.policy.__class__.__name__},
            )

        segment_profiles: list[ExecutionSegmentDriftProfile] = []
        for segment_type in selected_segments:
            baseline_groups = self._segment_rows(baseline, segment_type)
            current_groups = self._segment_rows(current, segment_type)
            for segment_name in sorted(set(baseline_groups) | set(current_groups)):
                segment_profiles.append(self.analyze_segment(
                    segment_type,
                    segment_name,
                    baseline_groups.get(segment_name, []),
                    current_groups.get(segment_name, []),
                    selected_metrics,
                ))

        metric_rejections = [reason for item in metric_profiles for reason in item.rejection_reasons]
        segment_rejections = [reason for item in segment_profiles for reason in item.rejection_reasons]
        rejections.extend(metric_rejections)
        rejections.extend(segment_rejections)
        rejections = list(dict.fromkeys(rejections))
        aggregate_psi = fmean(item.population_stability_index for item in metric_profiles)
        maximum_psi = max(item.population_stability_index for item in metric_profiles)
        score = self._weighted_score(metric_profiles)
        severity = self._worst_severity(item.drift_severity for item in metric_profiles)
        allowed = score >= self.policy.minimum_governance_score and not rejections
        if score < self.policy.minimum_governance_score:
            rejections.append("EXECUTION_GOVERNANCE_SCORE_BELOW_MINIMUM")
            allowed = False

        if insufficient and self.policy.allow_insufficient_data and not metric_rejections and score >= self.policy.minimum_governance_score:
            recommendation = "MONITOR_INSUFFICIENT_DATA"
        elif allowed and severity == "LOW":
            recommendation = "RETAIN_ACTIVE_ROUTES"
        elif allowed:
            recommendation = "REVIEW_EXECUTION_DRIFT"
        else:
            recommendation = "RESTRICT_OR_REVIEW_ROUTES"

        return ExecutionGovernanceProfile(
            valid=True,
            allowed=allowed,
            baseline_name=baseline_name,
            current_name=current_name,
            baseline_observation_count=len(baseline),
            current_observation_count=len(current),
            metric_count=len(metric_profiles),
            segment_count=sum(1 for item in segment_profiles if item.valid),
            aggregate_psi=aggregate_psi,
            maximum_metric_psi=maximum_psi,
            deteriorated_metric_count=sum(1 for item in metric_profiles if item.deteriorated),
            governance_score=score,
            governance_grade=self._grade(score),
            drift_severity=severity,
            recommendation=recommendation,
            baseline_profile=baseline_profile,
            current_profile=current_profile,
            metric_profiles=metric_profiles,
            segment_profiles=tuple(segment_profiles),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={
                "policy": self.policy.__class__.__name__,
                "metrics": list(selected_metrics),
                "segment_types": list(selected_segments),
            },
        )
