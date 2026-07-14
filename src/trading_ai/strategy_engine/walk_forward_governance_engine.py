from __future__ import annotations

from .walk_forward_governance_policy import WalkForwardGovernancePolicy
from .walk_forward_governance_profile import WalkForwardGovernanceProfile


class WalkForwardGovernanceEngine:
    def __init__(self, policy: WalkForwardGovernancePolicy | None = None):
        self.policy = policy or WalkForwardGovernancePolicy()

    @staticmethod
    def _f(obj, name, default=0.0):
        try:
            return float(getattr(obj, name, default) or default)
        except Exception:
            return float(default)

    @staticmethod
    def _s(obj, name, default="UNKNOWN"):
        return str(getattr(obj, name, default) or default).upper()

    def evaluate(self, champion_profile, challenger_profile, champion_version="champion", challenger_version="challenger"):
        p = self.policy
        rejections: list[str] = []
        warnings: list[str] = []
        if champion_profile is None or challenger_profile is None:
            rejections.append("WALK_FORWARD_GOVERNANCE_PROFILE_UNAVAILABLE")
            return WalkForwardGovernanceProfile(rejection_reasons=rejections)

        completed = int(getattr(challenger_profile, "completed_window_count", 0) or 0)
        c_score = self._f(champion_profile, "walk_forward_score")
        n_score = self._f(challenger_profile, "walk_forward_score")
        score_improvement = n_score - c_score
        return_improvement = self._f(challenger_profile, "aggregate_oos_return") - self._f(champion_profile, "aggregate_oos_return")
        sharpe_improvement = self._f(challenger_profile, "average_oos_sharpe") - self._f(champion_profile, "average_oos_sharpe")
        drawdown_deterioration = abs(min(0.0, self._f(challenger_profile, "worst_oos_drawdown_pct"))) - abs(min(0.0, self._f(champion_profile, "worst_oos_drawdown_pct")))
        degradation_deterioration = self._f(challenger_profile, "average_degradation_pct") - self._f(champion_profile, "average_degradation_pct")
        stability = self._f(challenger_profile, "parameter_stability_score")
        severity = self._s(challenger_profile, "risk_severity")

        checks = [
            (completed >= p.minimum_completed_windows, "INSUFFICIENT_CHALLENGER_WINDOWS"),
            (bool(getattr(challenger_profile, "valid", False)), "CHALLENGER_PROFILE_INVALID"),
            (bool(getattr(challenger_profile, "allowed", False)), "CHALLENGER_PROFILE_NOT_ALLOWED"),
            (n_score >= p.minimum_challenger_score, "CHALLENGER_SCORE_BELOW_MINIMUM"),
            (score_improvement >= p.minimum_score_improvement, "INSUFFICIENT_SCORE_IMPROVEMENT"),
            (return_improvement >= p.minimum_oos_return_improvement, "INSUFFICIENT_OOS_RETURN_IMPROVEMENT"),
            (sharpe_improvement >= p.minimum_sharpe_improvement, "INSUFFICIENT_SHARPE_IMPROVEMENT"),
            (drawdown_deterioration <= p.maximum_drawdown_deterioration_pct, "EXCESSIVE_DRAWDOWN_DETERIORATION"),
            (degradation_deterioration <= p.maximum_degradation_deterioration_pct, "EXCESSIVE_VALIDATION_TEST_DEGRADATION"),
            (stability >= p.minimum_parameter_stability, "PARAMETER_STABILITY_BELOW_MINIMUM"),
            (not p.reject_critical_severity or severity != "CRITICAL", "CRITICAL_CHALLENGER_RISK"),
        ]
        for passed, reason in checks:
            if not passed:
                rejections.append(reason)

        promotion_eligible = not rejections
        confidence = max(0.0, min(100.0, 50.0 + score_improvement * 3.0 + sharpe_improvement * 8.0 + stability * 0.2 - max(0.0, drawdown_deterioration) * 100.0))
        grade = "A" if confidence >= 85 else "B" if confidence >= 75 else "C" if confidence >= 65 else "D" if confidence >= 50 else "F"
        risk = "LOW" if promotion_eligible and confidence >= 75 else "MODERATE" if promotion_eligible else "SEVERE"
        if promotion_eligible and not p.automatic_promotion_enabled:
            warnings.append("AUTOMATIC_PROMOTION_DISABLED")

        return WalkForwardGovernanceProfile(
            valid=True,
            allowed=promotion_eligible,
            recommendation="PROMOTE_CHALLENGER" if promotion_eligible else "RETAIN_CHAMPION",
            champion_version=champion_version,
            challenger_version=challenger_version,
            champion_score=c_score,
            challenger_score=n_score,
            score_improvement=score_improvement,
            oos_return_improvement=return_improvement,
            sharpe_improvement=sharpe_improvement,
            drawdown_deterioration_pct=drawdown_deterioration,
            degradation_deterioration_pct=degradation_deterioration,
            promotion_eligible=promotion_eligible,
            confidence_score=confidence,
            governance_grade=grade,
            risk_severity=risk,
            champion_profile=champion_profile,
            challenger_profile=challenger_profile,
            warnings=warnings,
            rejection_reasons=rejections,
            metadata={"automatic_promotion_enabled": p.automatic_promotion_enabled},
        )
