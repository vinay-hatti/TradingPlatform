from __future__ import annotations

import math
from typing import Any

from trading_ai.strategy_engine.execution_champion_challenger_policy import ExecutionChampionChallengerPolicy
from trading_ai.strategy_engine.execution_champion_challenger_profile import (
    ExecutionChampionChallengerBatchProfile,
    ExecutionChampionChallengerProfile,
    ExecutionComparisonMetricProfile,
)


class ExecutionChampionChallengerEngine:
    """Institutional comparative evaluator for execution routing candidates."""

    _METRICS = (
        ("route_score", True, 0.22),
        ("average_shortfall_bps", False, 0.20),
        ("average_fill_ratio", True, 0.16),
        ("average_latency_seconds", False, 0.10),
        ("average_spread_bps", False, 0.10),
        ("average_market_impact_bps", False, 0.08),
        ("average_effective_spread_bps", False, 0.06),
        ("governance_score", True, 0.08),
    )

    def __init__(self, policy: ExecutionChampionChallengerPolicy | None = None):
        self.policy = policy or ExecutionChampionChallengerPolicy()

    @staticmethod
    def _value(item: Any, name: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            if name in item:
                return item.get(name, default)
            metadata = item.get("metadata", {}) or {}
            return metadata.get(name, default) if isinstance(metadata, dict) else default
        value = getattr(item, name, None)
        if value is not None:
            return value
        metadata = getattr(item, "metadata", {}) or {}
        return metadata.get(name, default) if isinstance(metadata, dict) else default

    @classmethod
    def _float(cls, item: Any, name: str, default: float = 0.0) -> float:
        try:
            value = float(cls._value(item, name, default) or default)
            return value if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def _int(cls, item: Any, name: str, default: int = 0) -> int:
        try:
            return int(float(cls._value(item, name, default) or default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"

    @staticmethod
    def _severity(allowed: bool, score: float, rejection_count: int) -> str:
        if rejection_count >= 3:
            return "CRITICAL"
        if not allowed:
            return "SEVERE"
        if score < 70:
            return "MODERATE"
        return "LOW"

    def _comparison(self, champion: Any, challenger: Any, metric: str, higher_is_better: bool, weight: float) -> ExecutionComparisonMetricProfile:
        champion_value = self._float(champion, metric)
        challenger_value = self._float(challenger, metric)
        absolute_change = challenger_value - champion_value
        denominator = abs(champion_value) if abs(champion_value) > 1e-12 else 1.0
        relative_change = absolute_change / denominator
        improvement = absolute_change if higher_is_better else -absolute_change
        normalized = max(-1.0, min(1.0, improvement / denominator))
        weighted_score = normalized * weight * 100.0
        favorable = improvement >= 0.0
        magnitude = abs(relative_change)
        severity = "LOW" if magnitude < 0.05 else "MODERATE" if magnitude < 0.15 else "SEVERE"
        return ExecutionComparisonMetricProfile(
            metric=metric,
            champion_value=champion_value,
            challenger_value=challenger_value,
            absolute_change=absolute_change,
            relative_change=relative_change,
            improvement=improvement,
            favorable=favorable,
            weight=weight,
            weighted_score=weighted_score,
            severity=severity,
            metadata={"higher_is_better": higher_is_better},
        )

    def evaluate(self, champion: Any, challenger: Any) -> ExecutionChampionChallengerProfile:
        if champion is None or challenger is None:
            return ExecutionChampionChallengerProfile(
                warnings=("Champion and challenger route profiles are required.",),
                rejection_reasons=("INSUFFICIENT_ROUTE_PROFILES",),
            )

        p = self.policy
        warnings: list[str] = []
        rejections: list[str] = []
        champion_type = str(self._value(champion, "route_type", "VENUE") or "VENUE").upper()
        challenger_type = str(self._value(challenger, "route_type", champion_type) or champion_type).upper()
        champion_count = self._int(champion, "observation_count")
        challenger_count = self._int(challenger, "observation_count")

        if p.require_same_route_type and champion_type != challenger_type:
            rejections.append("ROUTE_TYPE_MISMATCH")
        if champion_count < p.minimum_champion_observations:
            rejections.append("INSUFFICIENT_CHAMPION_OBSERVATIONS")
        if challenger_count < p.minimum_challenger_observations:
            rejections.append("INSUFFICIENT_CHALLENGER_OBSERVATIONS")

        comparisons = tuple(self._comparison(champion, challenger, *spec) for spec in self._METRICS)
        weighted_delta = sum(item.weighted_score for item in comparisons)
        evaluation_score = max(0.0, min(100.0, 50.0 + weighted_delta))

        route_score_improvement = self._float(challenger, "route_score") - self._float(champion, "route_score")
        shortfall_improvement = self._float(champion, "average_shortfall_bps") - self._float(challenger, "average_shortfall_bps")
        fill_change = self._float(challenger, "average_fill_ratio") - self._float(champion, "average_fill_ratio")
        latency_change = self._float(challenger, "average_latency_seconds") - self._float(champion, "average_latency_seconds")
        spread_change = self._float(challenger, "average_spread_bps") - self._float(champion, "average_spread_bps")
        market_impact_change = self._float(challenger, "average_market_impact_bps") - self._float(champion, "average_market_impact_bps")
        effective_spread_change = self._float(challenger, "average_effective_spread_bps") - self._float(champion, "average_effective_spread_bps")
        champion_gov = self._float(champion, "governance_score")
        challenger_gov = self._float(challenger, "governance_score")
        confidence = self._float(challenger, "confidence_score")

        if route_score_improvement < p.minimum_route_score_improvement:
            rejections.append("INSUFFICIENT_ROUTE_SCORE_IMPROVEMENT")
        if shortfall_improvement < p.minimum_shortfall_improvement_bps:
            rejections.append("SHORTFALL_NOT_IMPROVED")
        if fill_change < -p.maximum_fill_ratio_deterioration:
            rejections.append("FILL_RATIO_DETERIORATION_EXCEEDED")
        if latency_change > p.maximum_latency_deterioration_seconds:
            rejections.append("LATENCY_DETERIORATION_EXCEEDED")
        if spread_change > p.maximum_spread_deterioration_bps:
            rejections.append("SPREAD_DETERIORATION_EXCEEDED")
        if market_impact_change > p.maximum_market_impact_deterioration_bps:
            rejections.append("MARKET_IMPACT_DETERIORATION_EXCEEDED")
        if effective_spread_change > p.maximum_effective_spread_deterioration_bps:
            rejections.append("EFFECTIVE_SPREAD_DETERIORATION_EXCEEDED")
        if confidence < p.minimum_confidence_score:
            rejections.append("CHALLENGER_CONFIDENCE_BELOW_MINIMUM")
        if evaluation_score < p.minimum_evaluation_score:
            rejections.append("EVALUATION_SCORE_BELOW_MINIMUM")

        challenger_allowed = bool(self._value(challenger, "governance_allowed", True))
        challenger_severity = str(self._value(challenger, "governance_severity", "UNKNOWN") or "UNKNOWN").upper()
        if p.require_governance_approval and challenger_gov < p.minimum_governance_score:
            rejections.append("CHALLENGER_GOVERNANCE_SCORE_BELOW_MINIMUM")
        if p.require_governance_approval and not challenger_allowed:
            rejections.append("CHALLENGER_GOVERNANCE_REJECTED")
        if p.reject_severe_drift and challenger_severity in {"SEVERE", "CRITICAL"}:
            rejections.append("CHALLENGER_GOVERNANCE_DRIFT_TOO_HIGH")

        if 0.0 <= route_score_improvement < 5.0:
            warnings.append("Route-score improvement is positive but modest.")
        if challenger_gov < champion_gov:
            warnings.append("Challenger governance score is below the champion governance score.")
        if any(not metric.favorable for metric in comparisons):
            warnings.append("One or more execution metrics deteriorated versus the champion.")

        rejections = list(dict.fromkeys(rejections))
        allowed = not rejections
        recommendation = "PROMOTE_CHALLENGER" if allowed else "HOLD_CHAMPION"
        return ExecutionChampionChallengerProfile(
            valid=True,
            allowed=allowed,
            route_type=challenger_type,
            champion_version=str(self._value(champion, "version", "UNAVAILABLE")),
            challenger_version=str(self._value(challenger, "version", "UNAVAILABLE")),
            champion_route_name=str(self._value(champion, "route_name", "UNKNOWN")),
            challenger_route_name=str(self._value(challenger, "route_name", "UNKNOWN")),
            champion_observation_count=champion_count,
            challenger_observation_count=challenger_count,
            metric_comparisons=comparisons,
            route_score_improvement=route_score_improvement,
            shortfall_improvement_bps=shortfall_improvement,
            fill_ratio_change=fill_change,
            latency_change_seconds=latency_change,
            spread_change_bps=spread_change,
            market_impact_change_bps=market_impact_change,
            effective_spread_change_bps=effective_spread_change,
            champion_governance_score=champion_gov,
            challenger_governance_score=challenger_gov,
            evaluation_score=evaluation_score,
            confidence_score=confidence,
            evaluation_grade=self._grade(evaluation_score),
            governance_severity=self._severity(allowed, evaluation_score, len(rejections)),
            recommendation=recommendation,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(rejections),
            metadata={"favorable_metric_count": sum(m.favorable for m in comparisons), "metric_count": len(comparisons)},
        )

    def evaluate_batch(self, champion: Any, challengers: list[Any] | tuple[Any, ...]) -> ExecutionChampionChallengerBatchProfile:
        evaluations = tuple(self.evaluate(champion, challenger) for challenger in (challengers or ()))
        eligible = [item for item in evaluations if item.valid and item.allowed]
        ranked = sorted(eligible, key=lambda item: (item.evaluation_score, item.confidence_score), reverse=True)
        best = ranked[0] if ranked else None
        return ExecutionChampionChallengerBatchProfile(
            valid=champion is not None and bool(evaluations),
            champion_version=str(self._value(champion, "version", "UNAVAILABLE")) if champion is not None else "UNAVAILABLE",
            challenger_count=len(evaluations),
            eligible_count=len(eligible),
            best_challenger_version=best.challenger_version if best else "UNAVAILABLE",
            best_evaluation_score=best.evaluation_score if best else 0.0,
            recommendation="PROMOTE_BEST_CHALLENGER" if best else "NO_ELIGIBLE_CHALLENGER",
            evaluations=evaluations,
            warnings=() if best else ("No challenger satisfied institutional promotion policy.",),
            metadata={"ranking": [item.challenger_version for item in ranked]},
        )
