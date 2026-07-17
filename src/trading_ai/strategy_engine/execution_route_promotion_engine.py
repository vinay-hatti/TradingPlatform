from __future__ import annotations

from typing import Any

from trading_ai.strategy_engine.execution_route_governance_policy import ExecutionRouteGovernancePolicy
from trading_ai.strategy_engine.execution_route_registry_profile import ExecutionRoutePromotionProfile


class ExecutionRoutePromotionEngine:
    """Evaluate a challenger route against the active institutional champion."""

    def __init__(self, policy: ExecutionRouteGovernancePolicy | None = None):
        self.policy = policy or ExecutionRouteGovernancePolicy()

    @staticmethod
    def _value(item: Any, name: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    @classmethod
    def _float(cls, item: Any, name: str, default: float = 0.0) -> float:
        try:
            return float(cls._value(item, name, default) or default)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _int(cls, item: Any, name: str, default: int = 0) -> int:
        try:
            return int(float(cls._value(item, name, default) or default))
        except (TypeError, ValueError):
            return default

    def evaluate(self, champion: Any, challenger: Any) -> ExecutionRoutePromotionProfile:
        if champion is None or challenger is None:
            return ExecutionRoutePromotionProfile(
                warnings=("Champion and challenger route profiles are required.",),
                rejection_reasons=("INSUFFICIENT_ROUTE_PROFILES",),
            )

        p = self.policy
        warnings: list[str] = []
        rejections: list[str] = []

        champion_version = str(self._value(champion, "version", "UNAVAILABLE"))
        challenger_version = str(self._value(challenger, "version", "UNAVAILABLE"))
        route_type = str(self._value(challenger, "route_type", self._value(champion, "route_type", "VENUE"))).upper()

        champion_count = self._int(champion, "observation_count")
        challenger_count = self._int(challenger, "observation_count")
        if champion_count < p.minimum_champion_observations:
            rejections.append("INSUFFICIENT_CHAMPION_OBSERVATIONS")
        if challenger_count < p.minimum_challenger_observations:
            rejections.append("INSUFFICIENT_CHALLENGER_OBSERVATIONS")

        champion_score = self._float(champion, "route_score")
        challenger_score = self._float(challenger, "route_score")
        score_improvement = challenger_score - champion_score
        if challenger_score < p.minimum_route_score:
            rejections.append("CHALLENGER_ROUTE_SCORE_BELOW_MINIMUM")
        if self._float(challenger, "confidence_score") < p.minimum_confidence_score:
            rejections.append("CHALLENGER_CONFIDENCE_BELOW_MINIMUM")
        if score_improvement < p.minimum_score_improvement:
            rejections.append("INSUFFICIENT_ROUTE_SCORE_IMPROVEMENT")

        shortfall_improvement = self._float(champion, "average_shortfall_bps") - self._float(challenger, "average_shortfall_bps")
        fill_change = self._float(challenger, "average_fill_ratio") - self._float(champion, "average_fill_ratio")
        latency_change = self._float(challenger, "average_latency_seconds") - self._float(champion, "average_latency_seconds")
        spread_change = self._float(challenger, "average_spread_bps") - self._float(champion, "average_spread_bps")

        if shortfall_improvement < p.minimum_shortfall_improvement_bps:
            rejections.append("SHORTFALL_NOT_IMPROVED")
        if fill_change < -p.maximum_fill_ratio_deterioration:
            rejections.append("FILL_RATIO_DETERIORATION_EXCEEDED")
        if latency_change > p.maximum_latency_deterioration_seconds:
            rejections.append("LATENCY_DETERIORATION_EXCEEDED")
        if spread_change > p.maximum_spread_deterioration_bps:
            rejections.append("SPREAD_DETERIORATION_EXCEEDED")

        champion_gov = self._float(champion, "governance_score")
        challenger_gov = self._float(challenger, "governance_score")
        challenger_allowed = bool(self._value(challenger, "governance_allowed", True))
        challenger_severity = str(self._value(challenger, "governance_severity", "UNKNOWN") or "UNKNOWN").upper()
        if p.require_governance_approval and challenger_gov < p.minimum_governance_score:
            rejections.append("CHALLENGER_GOVERNANCE_SCORE_BELOW_MINIMUM")
        if p.require_challenger_allowed and not challenger_allowed:
            rejections.append("CHALLENGER_GOVERNANCE_REJECTED")
        if p.reject_severe_governance_drift and challenger_severity in {"SEVERE", "CRITICAL"}:
            rejections.append("CHALLENGER_GOVERNANCE_DRIFT_TOO_HIGH")

        if score_improvement < 5.0:
            warnings.append("Route score improvement is modest.")
        if challenger_gov < champion_gov:
            warnings.append("Challenger governance score is below the champion governance score.")

        promotion_score = max(0.0, min(100.0,
            50.0
            + score_improvement * 3.0
            + shortfall_improvement * 1.5
            + fill_change * 100.0
            - max(latency_change, 0.0) * 2.0
            - max(spread_change, 0.0) * 2.0
            + (challenger_gov - champion_gov) * 0.25
        ))
        allowed = not rejections
        grade = "A" if promotion_score >= 85 else "B" if promotion_score >= 70 else "C" if promotion_score >= 55 else "D" if promotion_score >= 40 else "F"
        severity = "LOW" if allowed and promotion_score >= 70 else "MODERATE" if allowed else "SEVERE"

        return ExecutionRoutePromotionProfile(
            valid=True,
            allowed=allowed,
            route_type=route_type,
            champion_version=champion_version,
            challenger_version=challenger_version,
            champion_route_name=str(self._value(champion, "route_name", "UNKNOWN")),
            challenger_route_name=str(self._value(challenger, "route_name", "UNKNOWN")),
            champion_route_score=champion_score,
            challenger_route_score=challenger_score,
            route_score_improvement=score_improvement,
            shortfall_improvement_bps=shortfall_improvement,
            fill_ratio_change=fill_change,
            latency_change_seconds=latency_change,
            spread_change_bps=spread_change,
            champion_governance_score=champion_gov,
            challenger_governance_score=challenger_gov,
            promotion_score=promotion_score,
            promotion_grade=grade,
            promotion_severity=severity,
            recommendation="PROMOTE_CHALLENGER" if allowed else "HOLD_CHAMPION",
            promoted=False,
            warnings=tuple(warnings),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={"champion_observation_count": champion_count, "challenger_observation_count": challenger_count},
        )
