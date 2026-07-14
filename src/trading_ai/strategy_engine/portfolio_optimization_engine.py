from __future__ import annotations

from collections import defaultdict
import math
from typing import Iterable

from trading_ai.strategy_engine.portfolio_optimization_policy import (
    PortfolioOptimizationPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_profile import (
    PortfolioOptimizationAllocation,
    PortfolioOptimizationCandidate,
    PortfolioOptimizationProfile,
)


class PortfolioOptimizationEngine:
    """
    Deterministic constrained portfolio optimizer.

    The engine complements the existing greedy PortfolioConstructor. It allocates
    capital in fixed increments to the candidate with the highest feasible
    marginal institutional objective until no additional allocation is feasible.
    """

    def __init__(self, policy: PortfolioOptimizationPolicy | None = None):
        self.policy = policy or PortfolioOptimizationPolicy()
        self.policy.validate()

    def optimize(
        self,
        candidates: Iterable[PortfolioOptimizationCandidate],
        initial_capital: float,
    ) -> PortfolioOptimizationProfile:
        capital = float(initial_capital or 0.0)
        if capital <= 0.0:
            return self._invalid_profile(capital, "INITIAL_CAPITAL_MUST_BE_POSITIVE")

        normalized, rejected = self._eligible_candidates(list(candidates))
        if not normalized:
            profile = self._invalid_profile(capital, "NO_ELIGIBLE_OPTIMIZATION_CANDIDATES")
            profile.candidate_count = len(list(candidates)) if not isinstance(candidates, list) else len(candidates)
            profile.rejected_candidates = rejected
            return profile

        max_exposure = capital * self.policy.maximum_portfolio_exposure_pct
        max_risk = capital * self.policy.maximum_total_risk_pct
        step = max(capital * self.policy.allocation_step_pct, self.policy.minimum_allocation_dollars)

        allocated = {item.candidate_id: 0.0 for item in normalized}
        selected_ids: set[str] = set()
        binding: set[str] = set()

        while True:
            best = None
            best_score = -math.inf
            for candidate in normalized:
                if candidate.candidate_id not in selected_ids and len(selected_ids) >= self.policy.maximum_positions:
                    continue
                proposed = min(step, max(candidate.capital_required - allocated[candidate.candidate_id], 0.0))
                if proposed <= 0.0:
                    continue
                feasible, reasons = self._feasible_increment(
                    candidate=candidate,
                    increment=proposed,
                    allocated=allocated,
                    candidates=normalized,
                    initial_capital=capital,
                    maximum_exposure=max_exposure,
                    maximum_risk=max_risk,
                )
                if not feasible:
                    binding.update(reasons)
                    continue
                score = self._marginal_score(candidate, allocated, normalized, capital)
                if score > best_score:
                    best = (candidate, proposed)
                    best_score = score
            if best is None:
                break
            candidate, proposed = best
            allocated[candidate.candidate_id] += proposed
            selected_ids.add(candidate.candidate_id)

        allocations = self._build_allocations(normalized, allocated, capital)
        if not allocations:
            profile = self._invalid_profile(capital, "OPTIMIZER_COULD_NOT_PRODUCE_FEASIBLE_ALLOCATION")
            profile.candidate_count = len(normalized) + len(rejected)
            profile.rejected_candidates = rejected
            profile.binding_constraints = sorted(binding)
            return profile

        return self._build_profile(
            candidates=normalized,
            allocations=allocations,
            rejected=rejected,
            initial_capital=capital,
            binding_constraints=sorted(binding),
        )

    def _eligible_candidates(self, candidates):
        eligible = []
        rejected = []
        seen = set()
        for index, candidate in enumerate(candidates):
            candidate_id = str(candidate.candidate_id or f"CANDIDATE_{index + 1}")
            if candidate_id in seen:
                rejected.append({"candidate_id": candidate_id, "reasons": ["DUPLICATE_CANDIDATE_ID"]})
                continue
            seen.add(candidate_id)
            reasons = []
            if candidate.capital_required <= 0.0:
                reasons.append("CAPITAL_REQUIRED_MUST_BE_POSITIVE")
            if candidate.maximum_loss < 0.0:
                reasons.append("MAXIMUM_LOSS_CANNOT_BE_NEGATIVE")
            if self.policy.reject_disallowed_candidates and not candidate.allowed:
                reasons.append("CANDIDATE_NOT_ALLOWED")
            quality = 0.50 * candidate.ranking_score + 0.50 * candidate.strategy_score
            if quality < self.policy.minimum_candidate_score:
                reasons.append("CANDIDATE_SCORE_BELOW_MINIMUM")
            if candidate.surface_score < self.policy.minimum_surface_score:
                reasons.append("SURFACE_SCORE_BELOW_MINIMUM")
            if self.policy.reject_critical_surface_risk and str(candidate.surface_severity).upper() == "CRITICAL":
                reasons.append("CRITICAL_SURFACE_RISK")
            if reasons:
                rejected.append({"candidate_id": candidate_id, "symbol": candidate.symbol, "strategy": candidate.strategy, "reasons": reasons})
                continue
            candidate.candidate_id = candidate_id
            eligible.append(candidate)
        return eligible, rejected

    def _feasible_increment(self, candidate, increment, allocated, candidates, initial_capital, maximum_exposure, maximum_risk):
        reasons = []
        total_after = sum(allocated.values()) + increment
        if total_after > maximum_exposure + 1e-9:
            reasons.append("MAXIMUM_PORTFOLIO_EXPOSURE")
        if allocated[candidate.candidate_id] + increment > initial_capital * self.policy.maximum_position_weight_pct + 1e-9:
            reasons.append("MAXIMUM_POSITION_WEIGHT")

        risk_after = 0.0
        group_allocations = defaultdict(float)
        greek_totals = defaultdict(float)
        for item in candidates:
            amount = allocated[item.candidate_id]
            if item.candidate_id == candidate.candidate_id:
                amount += increment
            multiplier = amount / item.capital_required if item.capital_required else 0.0
            risk_after += item.maximum_loss * multiplier
            group_allocations[("sector", item.sector)] += amount
            group_allocations[("strategy", item.strategy)] += amount
            group_allocations[("correlation", item.correlation_group)] += amount
            greek_totals["delta"] += item.delta * multiplier
            greek_totals["gamma"] += item.gamma * multiplier
            greek_totals["theta"] += item.theta * multiplier
            greek_totals["vega"] += item.vega * multiplier
            greek_totals["rho"] += item.rho * multiplier
        if risk_after > maximum_risk + 1e-9:
            reasons.append("MAXIMUM_TOTAL_RISK")
        limits = {
            ("sector", candidate.sector): self.policy.maximum_sector_weight_pct,
            ("strategy", candidate.strategy): self.policy.maximum_strategy_weight_pct,
            ("correlation", candidate.correlation_group): self.policy.maximum_correlation_group_weight_pct,
        }
        for key, limit in limits.items():
            if key[1] and group_allocations[key] > initial_capital * limit + 1e-9:
                reasons.append(f"MAXIMUM_{key[0].upper()}_WEIGHT")
        greek_limits = {
            "delta": self.policy.maximum_absolute_delta,
            "gamma": self.policy.maximum_absolute_gamma,
            "theta": self.policy.maximum_absolute_theta,
            "vega": self.policy.maximum_absolute_vega,
            "rho": self.policy.maximum_absolute_rho,
        }
        for name, limit in greek_limits.items():
            if limit > 0.0 and abs(greek_totals[name]) > limit + 1e-9:
                reasons.append(f"MAXIMUM_ABSOLUTE_{name.upper()}")
        return not reasons, reasons

    def _marginal_score(self, candidate, allocated, candidates, capital):
        expected_return = max(min(candidate.expected_return_pct, 2.0), -1.0)
        expected_component = (expected_return + 1.0) / 3.0 * 100.0
        quality = (
            self.policy.expected_return_weight * expected_component
            + self.policy.ranking_score_weight * candidate.ranking_score
            + self.policy.strategy_score_weight * candidate.strategy_score
            + self.policy.surface_score_weight * candidate.surface_score
        )
        current_sector = sum(allocated[item.candidate_id] for item in candidates if item.sector == candidate.sector)
        current_corr = sum(allocated[item.candidate_id] for item in candidates if item.correlation_group == candidate.correlation_group)
        diversification = 100.0 * (1.0 - min((current_sector + current_corr) / max(2.0 * capital, 1.0), 1.0))
        efficiency = min(max(candidate.expected_profit / max(candidate.capital_required, 1.0), -1.0), 2.0)
        efficiency = (efficiency + 1.0) / 3.0 * 100.0
        quality += self.policy.diversification_weight * diversification
        quality += self.policy.capital_efficiency_weight * efficiency
        severity_penalty = {"LOW": 0.0, "MODERATE": 8.0, "SEVERE": 20.0, "CRITICAL": 50.0}.get(str(candidate.surface_severity).upper(), 5.0)
        tail_penalty = self.policy.tail_risk_penalty_weight * severity_penalty
        return quality - tail_penalty

    def _build_allocations(self, candidates, allocated, capital):
        rows = []
        for candidate in candidates:
            amount = allocated[candidate.candidate_id]
            if amount + 1e-9 < self.policy.minimum_allocation_dollars:
                continue
            multiplier = amount / candidate.capital_required
            rows.append(PortfolioOptimizationAllocation(
                candidate_id=candidate.candidate_id,
                symbol=str(candidate.symbol).upper(),
                strategy=str(candidate.strategy).upper(),
                allocation_dollars=round(amount, 2),
                allocation_weight_pct=amount / capital,
                allocation_multiplier=multiplier,
                expected_profit=candidate.expected_profit * multiplier,
                maximum_loss=candidate.maximum_loss * multiplier,
                expected_return_pct=candidate.expected_return_pct,
                marginal_objective_score=self._marginal_score(candidate, allocated, candidates, capital),
                ranking_score=candidate.ranking_score,
                surface_score=candidate.surface_score,
                sector=str(candidate.sector or "UNKNOWN").upper(),
                correlation_group=str(candidate.correlation_group or "UNKNOWN").upper(),
                metadata=dict(candidate.metadata or {}),
            ))
        return sorted(rows, key=lambda item: item.allocation_dollars, reverse=True)

    def _build_profile(self, candidates, allocations, rejected, initial_capital, binding_constraints):
        total_allocated = sum(item.allocation_dollars for item in allocations)
        total_loss = sum(item.maximum_loss for item in allocations)
        expected_profit = sum(item.expected_profit for item in allocations)
        weights = [item.allocation_dollars / total_allocated for item in allocations] if total_allocated else []
        weighted_ranking = sum(item.ranking_score * weight for item, weight in zip(allocations, weights))
        weighted_surface = sum(item.surface_score * weight for item, weight in zip(allocations, weights))
        candidate_map = {item.candidate_id: item for item in candidates}
        weighted_strategy = sum(candidate_map[item.candidate_id].strategy_score * weight for item, weight in zip(allocations, weights))

        sector_weights = self._group_weights(allocations, "sector", total_allocated)
        strategy_weights = self._group_weights(allocations, "strategy", total_allocated)
        correlation_weights = self._group_weights(allocations, "correlation_group", total_allocated)
        hhi = sum(weight * weight for weight in weights)
        effective_positions = 1.0 / hhi if hhi > 0.0 else 0.0
        diversification = min(effective_positions / max(len(allocations), 1), 1.0) * 100.0
        concentration = max((row["weight_pct"] for row in sector_weights + correlation_weights), default=0.0) * 100.0
        efficiency = max(min(expected_profit / max(total_allocated, 1.0), 1.0), -1.0)
        efficiency_score = (efficiency + 1.0) * 50.0

        greek_totals = {name: 0.0 for name in ["delta", "gamma", "theta", "vega", "rho"]}
        for allocation in allocations:
            candidate = candidate_map[allocation.candidate_id]
            for name in greek_totals:
                greek_totals[name] += getattr(candidate, name) * allocation.allocation_multiplier
        limits = {
            "delta": self.policy.maximum_absolute_delta,
            "gamma": self.policy.maximum_absolute_gamma,
            "theta": self.policy.maximum_absolute_theta,
            "vega": self.policy.maximum_absolute_vega,
            "rho": self.policy.maximum_absolute_rho,
        }
        utilizations = [abs(greek_totals[name]) / limit for name, limit in limits.items() if limit > 0.0]
        greek_utilization = min(max(utilizations, default=0.0), 1.0) * 100.0

        objective = (
            0.25 * weighted_ranking
            + 0.15 * weighted_strategy
            + 0.20 * weighted_surface
            + 0.20 * diversification
            + 0.20 * efficiency_score
            - self.policy.concentration_penalty_weight * concentration
            - self.policy.greek_penalty_weight * greek_utilization
        )
        objective = max(min(objective, 100.0), 0.0)
        grade = "A" if objective >= 85 else "B" if objective >= 75 else "C" if objective >= 65 else "D" if objective >= 50 else "F"
        risk_pct = total_loss / initial_capital
        severity = "CRITICAL" if risk_pct >= 0.20 else "SEVERE" if risk_pct >= 0.12 else "MODERATE" if risk_pct >= 0.06 else "LOW"
        allowed = risk_pct <= self.policy.maximum_total_risk_pct and total_allocated <= initial_capital * self.policy.maximum_portfolio_exposure_pct
        warnings = []
        if concentration >= 70.0:
            warnings.append("HIGH_PORTFOLIO_CONCENTRATION")
        if greek_utilization >= 80.0:
            warnings.append("HIGH_GREEK_LIMIT_UTILIZATION")
        if objective < 50.0:
            warnings.append("LOW_OPTIMIZATION_OBJECTIVE_SCORE")
        return PortfolioOptimizationProfile(
            initial_capital=initial_capital,
            candidate_count=len(candidates) + len(rejected),
            selected_count=len(allocations),
            total_allocated_capital=total_allocated,
            portfolio_exposure_pct=total_allocated / initial_capital,
            reserve_cash=initial_capital - total_allocated,
            reserve_cash_pct=(initial_capital - total_allocated) / initial_capital,
            total_maximum_loss=total_loss,
            total_risk_pct=risk_pct,
            expected_portfolio_profit=expected_profit,
            expected_portfolio_return_pct=expected_profit / initial_capital,
            weighted_ranking_score=weighted_ranking,
            weighted_strategy_score=weighted_strategy,
            weighted_surface_score=weighted_surface,
            diversification_score=diversification,
            capital_efficiency_score=efficiency_score,
            concentration_score=concentration,
            greek_utilization_score=greek_utilization,
            objective_score=objective,
            optimization_grade=grade,
            risk_severity=severity,
            allowed=allowed,
            valid=True,
            allocations=allocations,
            rejected_candidates=rejected,
            sector_weights=sector_weights,
            strategy_weights=strategy_weights,
            correlation_group_weights=correlation_weights,
            greek_totals=greek_totals,
            binding_constraints=binding_constraints,
            rejection_reasons=[] if allowed else ["OPTIMIZED_PORTFOLIO_EXCEEDS_POLICY_LIMITS"],
            warnings=warnings,
            metadata={"optimizer": "DETERMINISTIC_INCREMENTAL_CONSTRAINED", "allocation_step_pct": self.policy.allocation_step_pct},
        )

    def _group_weights(self, allocations, field_name, total_allocated):
        grouped = defaultdict(float)
        for item in allocations:
            grouped[getattr(item, field_name) or "UNKNOWN"] += item.allocation_dollars
        return [
            {field_name: key, "allocation_dollars": value, "weight_pct": value / total_allocated if total_allocated else 0.0}
            for key, value in sorted(grouped.items(), key=lambda pair: pair[1], reverse=True)
        ]

    def _invalid_profile(self, initial_capital, reason):
        return PortfolioOptimizationProfile(
            initial_capital=max(float(initial_capital or 0.0), 0.0), candidate_count=0, selected_count=0,
            total_allocated_capital=0.0, portfolio_exposure_pct=0.0,
            reserve_cash=max(float(initial_capital or 0.0), 0.0), reserve_cash_pct=1.0 if initial_capital else 0.0,
            total_maximum_loss=0.0, total_risk_pct=0.0, expected_portfolio_profit=0.0,
            expected_portfolio_return_pct=0.0, weighted_ranking_score=0.0,
            weighted_strategy_score=0.0, weighted_surface_score=0.0,
            diversification_score=0.0, capital_efficiency_score=0.0,
            concentration_score=0.0, greek_utilization_score=0.0, objective_score=0.0,
            optimization_grade="F", risk_severity="UNKNOWN", allowed=False, valid=False,
            rejection_reasons=[reason],
        )
