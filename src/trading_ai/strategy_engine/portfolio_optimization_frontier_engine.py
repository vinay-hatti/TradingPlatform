from __future__ import annotations

from dataclasses import replace
from itertools import product
from statistics import mean
from typing import Any, Iterable

from trading_ai.strategy_engine.portfolio_optimization_frontier_policy import (
    PortfolioOptimizationFrontierPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_frontier_profile import (
    PortfolioOptimizationFrontierPoint,
    PortfolioOptimizationFrontierProfile,
)
from trading_ai.strategy_engine.portfolio_optimization_policy import (
    PortfolioOptimizationPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_service import (
    PortfolioOptimizationService,
)


class PortfolioOptimizationFrontierEngine:
    """Build a deterministic sensitivity frontier using the Phase 5 optimizer."""

    def __init__(
        self,
        base_policy: PortfolioOptimizationPolicy | None = None,
        frontier_policy: PortfolioOptimizationFrontierPolicy | None = None,
    ) -> None:
        self.base_policy = base_policy or PortfolioOptimizationPolicy()
        self.base_policy.validate()
        self.frontier_policy = frontier_policy or PortfolioOptimizationFrontierPolicy()
        self.frontier_policy.validate()

    def analyze(
        self,
        candidates: Iterable[Any],
        initial_capital: float,
    ) -> PortfolioOptimizationFrontierProfile:
        materialized = list(candidates)
        capital = float(initial_capital or 0.0)
        if capital <= 0.0:
            return self._invalid(capital, len(materialized), "INITIAL_CAPITAL_MUST_BE_POSITIVE")
        if not materialized:
            return self._invalid(capital, 0, "NO_OPTIMIZATION_CANDIDATES")

        points: list[PortfolioOptimizationFrontierPoint] = []
        combinations = self._constraint_combinations()
        for index, (exposure, risk, concentration) in enumerate(combinations, start=1):
            scenario_policy = replace(
                self.base_policy,
                maximum_portfolio_exposure_pct=exposure,
                maximum_total_risk_pct=risk,
                reserve_cash_pct=min(self.base_policy.reserve_cash_pct, max(0.0, 1.0 - exposure)),
                maximum_sector_weight_pct=concentration,
                maximum_strategy_weight_pct=max(concentration, self.base_policy.maximum_strategy_weight_pct),
                maximum_correlation_group_weight_pct=concentration,
            )
            scenario_policy.validate()
            result = PortfolioOptimizationService(policy=scenario_policy).optimize(
                materialized,
                capital,
            )
            weights = {
                allocation.candidate_id: float(allocation.allocation_weight_pct)
                for allocation in result.allocations
            }
            points.append(
                PortfolioOptimizationFrontierPoint(
                    point_id=f"FRONTIER_{index:03d}",
                    maximum_exposure_pct=exposure,
                    maximum_risk_pct=risk,
                    maximum_concentration_pct=concentration,
                    selected_count=result.selected_count,
                    allocated_capital=result.total_allocated_capital,
                    exposure_pct=result.portfolio_exposure_pct,
                    maximum_loss=result.total_maximum_loss,
                    risk_pct=result.total_risk_pct,
                    expected_profit=result.expected_portfolio_profit,
                    expected_return_pct=result.expected_portfolio_return_pct,
                    objective_score=result.objective_score,
                    diversification_score=result.diversification_score,
                    concentration_score=result.concentration_score,
                    greek_utilization_score=result.greek_utilization_score,
                    optimization_grade=result.optimization_grade,
                    risk_severity=result.risk_severity,
                    allowed=result.allowed,
                    valid=result.valid,
                    allocation_ids=sorted(weights),
                    allocation_weights=weights,
                    binding_constraints=list(result.binding_constraints),
                    warnings=list(result.warnings),
                    rejection_reasons=list(result.rejection_reasons),
                    metadata={
                        "sector_weights": result.sector_weights,
                        "strategy_weights": result.strategy_weights,
                        "correlation_group_weights": result.correlation_group_weights,
                    },
                )
            )

        valid_points = [point for point in points if point.valid and point.allowed]
        if len(valid_points) < self.frontier_policy.minimum_valid_points:
            profile = self._invalid(capital, len(materialized), "INSUFFICIENT_VALID_FRONTIER_POINTS")
            profile.points = points
            profile.point_count = len(points)
            profile.valid_point_count = len(valid_points)
            return profile

        self._mark_pareto(valid_points)
        pareto_points = [point for point in valid_points if point.pareto_efficient]
        best = max(
            valid_points,
            key=lambda point: (
                point.objective_score,
                point.expected_return_pct,
                -point.risk_pct,
                point.diversification_score,
            ),
        )
        selection_stability, allocation_stability = self._stability(valid_points)
        objectives = [point.objective_score for point in valid_points]
        returns = [point.expected_return_pct for point in valid_points]
        risks = [point.risk_pct for point in valid_points]
        objective_range = max(objectives) - min(objectives)
        return_range = max(returns) - min(returns)
        risk_range = max(risks) - min(risks)
        sensitivity = self._sensitivity_score(objective_range, return_range, risk_range)
        frontier_score = self._frontier_score(
            best.objective_score,
            selection_stability,
            allocation_stability,
            sensitivity,
            len(pareto_points),
            len(valid_points),
        )
        grade = self._grade(frontier_score)
        severity = self._severity(best.risk_pct, sensitivity)
        warnings: list[str] = []
        if selection_stability < 60.0:
            warnings.append("LOW_SELECTION_STABILITY")
        if allocation_stability < 60.0:
            warnings.append("LOW_ALLOCATION_STABILITY")
        if sensitivity >= 70.0:
            warnings.append("HIGH_CONSTRAINT_SENSITIVITY")
        if len(pareto_points) <= 1:
            warnings.append("LIMITED_EFFICIENT_FRONTIER_BREADTH")

        return PortfolioOptimizationFrontierProfile(
            initial_capital=capital,
            candidate_count=len(materialized),
            point_count=len(points),
            valid_point_count=len(valid_points),
            pareto_point_count=len(pareto_points),
            best_point_id=best.point_id,
            best_objective_score=best.objective_score,
            best_expected_return_pct=best.expected_return_pct,
            lowest_risk_pct=min(risks),
            highest_expected_return_pct=max(returns),
            objective_range=objective_range,
            expected_return_range=return_range,
            risk_range=risk_range,
            selection_stability_score=selection_stability,
            allocation_stability_score=allocation_stability,
            constraint_sensitivity_score=sensitivity,
            frontier_score=frontier_score,
            frontier_grade=grade,
            risk_severity=severity,
            allowed=True,
            valid=True,
            points=points,
            pareto_points=pareto_points,
            warnings=warnings,
            metadata={
                "method": "DETERMINISTIC_CONSTRAINT_SWEEP",
                "base_policy": self.base_policy.__dict__.copy(),
                "frontier_policy": self.frontier_policy.__dict__.copy(),
            },
        )

    def _constraint_combinations(self) -> list[tuple[float, float, float]]:
        concentrations = (
            self.frontier_policy.concentration_levels
            if self.frontier_policy.include_concentration_sweep
            else (self.base_policy.maximum_sector_weight_pct,)
        )
        combinations = list(
            product(
                sorted(set(self.frontier_policy.exposure_levels)),
                sorted(set(self.frontier_policy.risk_levels)),
                sorted(set(concentrations)),
            )
        )
        return combinations[: self.frontier_policy.maximum_points]

    @staticmethod
    def _mark_pareto(points: list[PortfolioOptimizationFrontierPoint]) -> None:
        for point in points:
            dominated = False
            for other in points:
                if other is point:
                    continue
                no_worse = (
                    other.risk_pct <= point.risk_pct + 1e-12
                    and other.expected_return_pct >= point.expected_return_pct - 1e-12
                    and other.objective_score >= point.objective_score - 1e-12
                )
                strictly_better = (
                    other.risk_pct < point.risk_pct - 1e-12
                    or other.expected_return_pct > point.expected_return_pct + 1e-12
                    or other.objective_score > point.objective_score + 1e-12
                )
                if no_worse and strictly_better:
                    dominated = True
                    break
            point.pareto_efficient = not dominated

    def _stability(self, points: list[PortfolioOptimizationFrontierPoint]) -> tuple[float, float]:
        ordered = sorted(
            points,
            key=lambda point: (
                point.maximum_exposure_pct,
                point.maximum_risk_pct,
                point.maximum_concentration_pct,
            ),
        )
        if len(ordered) < 2:
            return 100.0, 100.0
        selection_scores: list[float] = []
        allocation_scores: list[float] = []
        for left, right in zip(ordered, ordered[1:]):
            left_ids = set(left.allocation_ids)
            right_ids = set(right.allocation_ids)
            union = left_ids | right_ids
            selection_scores.append(100.0 if not union else 100.0 * len(left_ids & right_ids) / len(union))
            all_ids = union
            drift = sum(
                abs(left.allocation_weights.get(candidate_id, 0.0) - right.allocation_weights.get(candidate_id, 0.0))
                for candidate_id in all_ids
            )
            normalized_drift = min(drift / 2.0, 1.0)
            allocation_scores.append(100.0 * (1.0 - normalized_drift))
        return mean(selection_scores), mean(allocation_scores)

    @staticmethod
    def _sensitivity_score(objective_range: float, return_range: float, risk_range: float) -> float:
        objective_component = min(objective_range / 25.0, 1.0)
        return_component = min(return_range / 0.10, 1.0)
        risk_component = min(risk_range / 0.10, 1.0)
        return 100.0 * (0.40 * objective_component + 0.35 * return_component + 0.25 * risk_component)

    @staticmethod
    def _frontier_score(
        best_objective: float,
        selection_stability: float,
        allocation_stability: float,
        sensitivity: float,
        pareto_count: int,
        valid_count: int,
    ) -> float:
        breadth = 100.0 * min(pareto_count / max(valid_count, 1), 1.0)
        score = (
            0.40 * best_objective
            + 0.20 * selection_stability
            + 0.20 * allocation_stability
            + 0.10 * (100.0 - sensitivity)
            + 0.10 * breadth
        )
        return max(0.0, min(score, 100.0))

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85.0 else "B" if score >= 75.0 else "C" if score >= 65.0 else "D" if score >= 50.0 else "F"

    @staticmethod
    def _severity(risk_pct: float, sensitivity: float) -> str:
        if risk_pct >= 0.20 or sensitivity >= 85.0:
            return "CRITICAL"
        if risk_pct >= 0.12 or sensitivity >= 70.0:
            return "SEVERE"
        if risk_pct >= 0.06 or sensitivity >= 45.0:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def _invalid(
        initial_capital: float,
        candidate_count: int,
        reason: str,
    ) -> PortfolioOptimizationFrontierProfile:
        return PortfolioOptimizationFrontierProfile(
            initial_capital=max(float(initial_capital or 0.0), 0.0),
            candidate_count=candidate_count,
            point_count=0,
            valid_point_count=0,
            pareto_point_count=0,
            best_point_id=None,
            best_objective_score=0.0,
            best_expected_return_pct=0.0,
            lowest_risk_pct=0.0,
            highest_expected_return_pct=0.0,
            objective_range=0.0,
            expected_return_range=0.0,
            risk_range=0.0,
            selection_stability_score=0.0,
            allocation_stability_score=0.0,
            constraint_sensitivity_score=0.0,
            frontier_score=0.0,
            frontier_grade="F",
            risk_severity="UNKNOWN",
            allowed=False,
            valid=False,
            rejection_reasons=[reason],
        )
