from __future__ import annotations

from .market_regime_governance_policy import MarketRegimeGovernancePolicy
from .market_regime_governance_profile import MarketRegimeGovernanceProfile


class MarketRegimeGovernanceEngine:
    def __init__(self, policy: MarketRegimeGovernancePolicy | None = None):
        self.policy = policy or MarketRegimeGovernancePolicy()

    @staticmethod
    def _v(obj, name, default=0.0):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def evaluate(self, champion_metrics, challenger_metrics, drift_profile=None, champion_version="champion", challenger_version="challenger"):
        p = self.policy
        rejections: list[str] = []
        warnings: list[str] = []
        observations = int(self._v(challenger_metrics, "observation_count", 0) or 0)
        c_acc = float(self._v(champion_metrics, "detection_accuracy", 0.0) or 0.0)
        n_acc = float(self._v(challenger_metrics, "detection_accuracy", 0.0) or 0.0)
        accuracy_improvement = n_acc - c_acc
        forecast_improvement = float(self._v(challenger_metrics, "forecast_accuracy", 0.0) or 0.0) - float(self._v(champion_metrics, "forecast_accuracy", 0.0) or 0.0)
        transition_improvement = float(self._v(challenger_metrics, "transition_f1", 0.0) or 0.0) - float(self._v(champion_metrics, "transition_f1", 0.0) or 0.0)
        fp_deterioration = float(self._v(challenger_metrics, "critical_false_positive_rate", 0.0) or 0.0) - float(self._v(champion_metrics, "critical_false_positive_rate", 0.0) or 0.0)
        c_score = float(self._v(champion_metrics, "model_score", 0.0) or 0.0)
        n_score = float(self._v(challenger_metrics, "model_score", 0.0) or 0.0)

        checks = [
            (observations >= p.minimum_evaluation_observations, "INSUFFICIENT_GOVERNANCE_OBSERVATIONS"),
            (accuracy_improvement >= p.minimum_accuracy_improvement, "INSUFFICIENT_DETECTION_ACCURACY_IMPROVEMENT"),
            (forecast_improvement >= p.minimum_forecast_accuracy_improvement, "INSUFFICIENT_FORECAST_ACCURACY_IMPROVEMENT"),
            (transition_improvement >= p.minimum_transition_f1_improvement, "INSUFFICIENT_TRANSITION_F1_IMPROVEMENT"),
            (fp_deterioration <= p.maximum_critical_false_positive_deterioration, "EXCESSIVE_CRITICAL_FALSE_POSITIVE_DETERIORATION"),
            (n_score >= p.minimum_challenger_score, "CHALLENGER_REGIME_MODEL_SCORE_BELOW_MINIMUM"),
            (not p.reject_critical_drift or getattr(drift_profile, "drift_severity", "LOW") != "CRITICAL", "CRITICAL_REGIME_DRIFT"),
        ]
        for passed, reason in checks:
            if not passed:
                rejections.append(reason)
        eligible = not rejections
        confidence = max(0.0, min(100.0, 55.0 + accuracy_improvement * 500.0 + forecast_improvement * 250.0 + transition_improvement * 150.0 + (n_score - c_score) * 0.5 - max(0.0, fp_deterioration) * 500.0))
        grade = "A" if confidence >= 85 else "B" if confidence >= 75 else "C" if confidence >= 65 else "D" if confidence >= 50 else "F"
        severity = "LOW" if eligible and confidence >= 75 else "MODERATE" if eligible else "SEVERE"
        if eligible and not p.automatic_promotion_enabled:
            warnings.append("AUTOMATIC_REGIME_MODEL_PROMOTION_DISABLED")
        return MarketRegimeGovernanceProfile(
            valid=True,
            allowed=eligible,
            recommendation="PROMOTE_CHALLENGER" if eligible else "RETAIN_CHAMPION",
            champion_version=champion_version,
            challenger_version=challenger_version,
            evaluation_observation_count=observations,
            champion_accuracy=c_acc,
            challenger_accuracy=n_acc,
            accuracy_improvement=accuracy_improvement,
            forecast_accuracy_improvement=forecast_improvement,
            transition_f1_improvement=transition_improvement,
            critical_false_positive_deterioration=fp_deterioration,
            champion_score=c_score,
            challenger_score=n_score,
            promotion_eligible=eligible,
            confidence_score=confidence,
            governance_grade=grade,
            risk_severity=severity,
            drift_profile=drift_profile,
            warnings=warnings,
            rejection_reasons=rejections,
            metadata={"automatic_promotion_enabled": p.automatic_promotion_enabled},
        )
