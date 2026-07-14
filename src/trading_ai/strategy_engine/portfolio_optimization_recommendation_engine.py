from __future__ import annotations

from dataclasses import replace

from trading_ai.strategy_engine.portfolio_optimization_policy import PortfolioOptimizationPolicy
from trading_ai.strategy_engine.portfolio_optimization_recommendation_policy import PortfolioOptimizationRecommendationPolicy
from trading_ai.strategy_engine.portfolio_optimization_recommendation_profile import PortfolioOptimizationPolicyRecommendation


class PortfolioOptimizationRecommendationEngine:
    def __init__(self, policy: PortfolioOptimizationRecommendationPolicy | None = None) -> None:
        self.policy = policy or PortfolioOptimizationRecommendationPolicy()
        self.policy.validate()

    def recommend(self, frontier_profile, base_policy: PortfolioOptimizationPolicy | None = None):
        base_policy = base_policy or PortfolioOptimizationPolicy()
        if frontier_profile is None or not bool(getattr(frontier_profile, "valid", False)):
            return self._invalid("OPTIMIZATION_FRONTIER_UNAVAILABLE")
        points = list(getattr(frontier_profile, "pareto_points", []) or [])
        if not points or not self.policy.prefer_pareto_points:
            points = [p for p in getattr(frontier_profile, "points", []) or [] if bool(getattr(p, "valid", False))]
        if not points:
            return self._invalid("NO_VALID_FRONTIER_POINT")
        best_id = getattr(frontier_profile, "best_point_id", None)
        point = next((p for p in points if getattr(p, "point_id", None) == best_id), None)
        if point is None:
            point = max(points, key=lambda p: (float(getattr(p, "objective_score", 0.0)), float(getattr(p, "expected_return_pct", 0.0)), -float(getattr(p, "risk_pct", 0.0))))
        stability = min(float(getattr(frontier_profile, "selection_stability_score", 0.0)), float(getattr(frontier_profile, "allocation_stability_score", 0.0)))
        sensitivity = float(getattr(frontier_profile, "constraint_sensitivity_score", 100.0))
        frontier_score = float(getattr(frontier_profile, "frontier_score", 0.0))
        severity = str(getattr(frontier_profile, "risk_severity", "UNKNOWN") or "UNKNOWN").upper()
        confidence = max(0.0, min(100.0, 0.45 * frontier_score + 0.35 * stability + 0.20 * (100.0 - sensitivity)))
        reasons=[]; warnings=[]
        if frontier_score < self.policy.minimum_frontier_score: reasons.append("FRONTIER_SCORE_BELOW_MINIMUM")
        if stability < self.policy.minimum_stability_score: reasons.append("FRONTIER_STABILITY_BELOW_MINIMUM")
        if sensitivity > self.policy.maximum_constraint_sensitivity_score: reasons.append("FRONTIER_CONSTRAINT_SENSITIVITY_TOO_HIGH")
        if self.policy.reject_critical_frontier and severity == "CRITICAL": reasons.append("CRITICAL_FRONTIER_RISK")
        allowed = not reasons
        if sensitivity > 50.0: warnings.append("Portfolio allocation is materially sensitive to policy constraints")
        if stability < 75.0: warnings.append("Portfolio allocation stability is below institutional target")
        concentration=float(getattr(point, "maximum_concentration_pct", base_policy.maximum_sector_weight_pct))
        recommended = replace(base_policy, maximum_portfolio_exposure_pct=float(point.maximum_exposure_pct), maximum_total_risk_pct=float(point.maximum_risk_pct), maximum_sector_weight_pct=concentration, maximum_strategy_weight_pct=concentration, maximum_correlation_group_weight_pct=concentration)
        grade = "A" if confidence >= 85 else "B" if confidence >= 75 else "C" if confidence >= 65 else "D" if confidence >= 50 else "F"
        return PortfolioOptimizationPolicyRecommendation(source_point_id=str(point.point_id), maximum_portfolio_exposure_pct=float(point.maximum_exposure_pct), maximum_total_risk_pct=float(point.maximum_risk_pct), maximum_sector_weight_pct=concentration, maximum_strategy_weight_pct=concentration, maximum_correlation_group_weight_pct=concentration, expected_return_pct=float(point.expected_return_pct), objective_score=float(point.objective_score), portfolio_risk_pct=float(point.risk_pct), selected_count=int(point.selected_count), confidence_score=confidence, recommendation_grade=grade, risk_severity=severity, allowed=allowed, valid=True, recommended_policy=recommended, rejection_reasons=reasons, warnings=warnings, metadata={"frontier_score": frontier_score, "stability_score": stability, "constraint_sensitivity_score": sensitivity})

    @staticmethod
    def _invalid(reason):
        return PortfolioOptimizationPolicyRecommendation(source_point_id=None, maximum_portfolio_exposure_pct=0.0, maximum_total_risk_pct=0.0, maximum_sector_weight_pct=0.0, maximum_strategy_weight_pct=0.0, maximum_correlation_group_weight_pct=0.0, expected_return_pct=0.0, objective_score=0.0, portfolio_risk_pct=0.0, selected_count=0, confidence_score=0.0, recommendation_grade="F", risk_severity="UNKNOWN", allowed=False, valid=False, rejection_reasons=[reason])
