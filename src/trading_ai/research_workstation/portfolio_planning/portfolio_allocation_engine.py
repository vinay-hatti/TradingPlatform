from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Mapping

from .portfolio_allocation_policy import PortfolioAllocationPolicy
from .portfolio_allocation_profile import (
    AllocationCandidateProfile,
    AllocationDecisionProfile,
    ExposureAnalyticsProfile,
    PortfolioAllocationProfile,
    PortfolioHealthProfile,
    PositionSizingProfile,
)


class PortfolioAllocationEngine:
    def __init__(
        self,
        policy: PortfolioAllocationPolicy | None = None,
    ) -> None:
        self.policy = policy or PortfolioAllocationPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def _risk_severity(
        rejection_count: int,
        warning_count: int,
    ) -> str:
        if rejection_count >= 2:
            return "CRITICAL"
        if rejection_count == 1:
            return "HIGH"
        if warning_count >= 3:
            return "MODERATE"
        if warning_count:
            return "LOW"
        return "NONE"

    @staticmethod
    def _bounded_contracts(
        budget: float,
        per_contract: float,
        cap: int,
    ) -> int:
        if per_contract <= 0:
            return cap
        return max(0, min(cap, math.floor(budget / per_contract)))

    @staticmethod
    def _kelly_fraction(candidate: AllocationCandidateProfile) -> float:
        win_probability = min(
            1.0,
            max(0.0, candidate.probability_of_profit),
        )
        loss_probability = 1.0 - win_probability
        if candidate.risk_per_contract <= 0:
            return 0.0
        reward_ratio = (
            candidate.maximum_profit_per_contract
            / candidate.risk_per_contract
        )
        if reward_ratio <= 0:
            return 0.0
        fraction = (
            win_probability
            - (loss_probability / reward_ratio)
        )
        return max(0.0, min(1.0, fraction))

    def _liquidity_haircut(
        self,
        candidate: AllocationCandidateProfile,
    ) -> float:
        normalized = max(
            self.policy.liquidity_haircut_floor,
            min(1.0, candidate.liquidity_score / 100.0),
        )
        return round(normalized, 6)

    def _size_candidate(
        self,
        *,
        candidate: AllocationCandidateProfile,
        account_equity: float,
        per_candidate_risk_budget: float,
    ) -> PositionSizingProfile:
        cap = min(
            candidate.requested_contracts,
            candidate.maximum_contracts,
            self.policy.maximum_contracts_per_position,
        )
        symbol_budget = (
            account_equity * self.policy.maximum_symbol_risk_pct
        )
        risk_budget = min(symbol_budget, per_candidate_risk_budget)

        fixed_fractional = self._bounded_contracts(
            risk_budget,
            candidate.risk_per_contract,
            cap,
        )

        kelly = self._kelly_fraction(candidate)
        fractional_kelly = (
            kelly * self.policy.use_fractional_kelly
        )
        kelly_budget = account_equity * fractional_kelly
        kelly_contracts = self._bounded_contracts(
            min(kelly_budget, risk_budget),
            candidate.risk_per_contract,
            cap,
        )

        volatility_budget = (
            account_equity
            * self.policy.target_portfolio_volatility_pct
        )
        volatility_denom = max(
            0.000001,
            candidate.risk_per_contract
            * max(candidate.annualized_volatility_pct, 0.01),
        )
        volatility_target = max(
            0,
            min(cap, math.floor(volatility_budget / volatility_denom)),
        )

        risk_budget_contracts = self._bounded_contracts(
            risk_budget,
            candidate.risk_per_contract,
            cap,
        )

        es_budget = (
            account_equity
            * self.policy.expected_shortfall_limit_pct
        )
        expected_shortfall_contracts = self._bounded_contracts(
            min(es_budget, risk_budget),
            max(
                candidate.expected_shortfall_per_contract,
                candidate.risk_per_contract * 0.25,
            ),
            cap,
        )

        liquidity_haircut = self._liquidity_haircut(candidate)
        raw_minimum = min(
            fixed_fractional,
            kelly_contracts,
            volatility_target,
            risk_budget_contracts,
            expected_shortfall_contracts,
            cap,
        )
        liquidity_adjusted = math.floor(
            raw_minimum * liquidity_haircut
        )
        if (
            liquidity_adjusted < self.policy.minimum_contracts
            and raw_minimum >= self.policy.minimum_contracts
            and liquidity_haircut >= 0.50
        ):
            liquidity_adjusted = self.policy.minimum_contracts

        recommended = max(0, liquidity_adjusted)
        constraints = {
            "FIXED_FRACTIONAL": fixed_fractional,
            "KELLY": kelly_contracts,
            "VOLATILITY_TARGET": volatility_target,
            "RISK_BUDGET": risk_budget_contracts,
            "EXPECTED_SHORTFALL": expected_shortfall_contracts,
            "LIQUIDITY": liquidity_adjusted,
            "REQUESTED_CAP": cap,
        }
        binding_constraint = min(
            constraints,
            key=lambda key: constraints[key],
        )

        return PositionSizingProfile(
            candidate_id=candidate.candidate_id,
            fixed_fractional_contracts=fixed_fractional,
            kelly_fraction=round(fractional_kelly, 6),
            kelly_contracts=kelly_contracts,
            volatility_target_contracts=volatility_target,
            risk_budget_contracts=risk_budget_contracts,
            expected_shortfall_contracts=expected_shortfall_contracts,
            liquidity_adjusted_contracts=liquidity_adjusted,
            recommended_contracts=recommended,
            binding_constraint=binding_constraint,
            liquidity_haircut=liquidity_haircut,
            maximum_position_risk=round(
                recommended * candidate.risk_per_contract,
                6,
            ),
            maximum_position_buying_power=round(
                recommended
                * candidate.buying_power_per_contract,
                6,
            ),
        )

    @staticmethod
    def _correlation(
        left: str,
        right: str,
        correlations: Mapping[tuple[str, str], float],
    ) -> float:
        if left == right:
            return 1.0
        return float(
            correlations.get(
                (left, right),
                correlations.get((right, left), 0.0),
            )
        )

    def allocate(
        self,
        *,
        account_equity: float,
        candidates: Iterable[AllocationCandidateProfile],
        correlations: Mapping[tuple[str, str], float] | None = None,
    ) -> PortfolioAllocationProfile:
        if account_equity <= 0:
            raise ValueError("Account equity must be positive.")

        candidates_tuple = tuple(candidates)
        if not candidates_tuple:
            raise ValueError("At least one candidate is required.")

        correlations = correlations or {}
        portfolio_risk_budget = (
            account_equity * self.policy.maximum_portfolio_risk_pct
        )
        buying_power_budget = (
            account_equity * self.policy.maximum_buying_power_pct
        )
        per_candidate_risk_budget = (
            portfolio_risk_budget / len(candidates_tuple)
        )

        sizing = tuple(
            self._size_candidate(
                candidate=candidate,
                account_equity=account_equity,
                per_candidate_risk_budget=per_candidate_risk_budget,
            )
            for candidate in candidates_tuple
        )
        sizing_by_id = {
            item.candidate_id: item
            for item in sizing
        }

        ranked = sorted(
            candidates_tuple,
            key=lambda candidate: (
                candidate.expected_return_pct
                * candidate.probability_of_profit
                * max(candidate.liquidity_score, 1.0)
            ),
            reverse=True,
        )

        total_risk = 0.0
        total_bp = 0.0
        symbol_risk: dict[str, float] = defaultdict(float)
        sector_risk: dict[str, float] = defaultdict(float)
        strategy_risk: dict[str, float] = defaultdict(float)
        selected: list[tuple[AllocationCandidateProfile, int]] = []
        decisions_by_id: dict[str, AllocationDecisionProfile] = {}

        for candidate in ranked:
            size = sizing_by_id[candidate.candidate_id]
            contracts = size.recommended_contracts
            warnings: list[str] = []
            rejections: list[str] = []

            if contracts <= 0:
                rejections.append(
                    "No contracts satisfy sizing constraints."
                )

            requested_risk = contracts * candidate.risk_per_contract
            requested_bp = (
                contracts * candidate.buying_power_per_contract
            )

            remaining_portfolio_risk = max(
                0.0, portfolio_risk_budget - total_risk
            )
            remaining_bp = max(
                0.0, buying_power_budget - total_bp
            )
            remaining_symbol = max(
                0.0,
                account_equity
                * self.policy.maximum_symbol_risk_pct
                - symbol_risk[candidate.symbol],
            )
            remaining_sector = max(
                0.0,
                account_equity
                * self.policy.maximum_sector_risk_pct
                - sector_risk[candidate.sector],
            )
            remaining_strategy = max(
                0.0,
                account_equity
                * self.policy.maximum_strategy_risk_pct
                - strategy_risk[candidate.strategy_name],
            )

            risk_contract_cap = min(
                self._bounded_contracts(
                    remaining_portfolio_risk,
                    candidate.risk_per_contract,
                    contracts,
                ),
                self._bounded_contracts(
                    remaining_symbol,
                    candidate.risk_per_contract,
                    contracts,
                ),
                self._bounded_contracts(
                    remaining_sector,
                    candidate.risk_per_contract,
                    contracts,
                ),
                self._bounded_contracts(
                    remaining_strategy,
                    candidate.risk_per_contract,
                    contracts,
                ),
                self._bounded_contracts(
                    remaining_bp,
                    candidate.buying_power_per_contract,
                    contracts,
                ),
            )

            correlation_cap = contracts
            correlated_risk = 0.0
            for selected_candidate, selected_contracts in selected:
                correlation = abs(
                    self._correlation(
                        candidate.symbol,
                        selected_candidate.symbol,
                        correlations,
                    )
                )
                if correlation > self.policy.maximum_pairwise_correlation:
                    warnings.append(
                        f"High correlation with "
                        f"{selected_candidate.symbol}: {correlation:.2f}."
                    )
                    correlated_risk += (
                        selected_contracts
                        * selected_candidate.risk_per_contract
                    )

            remaining_correlated_risk = max(
                0.0,
                account_equity
                * self.policy.maximum_correlated_risk_pct
                - correlated_risk,
            )
            correlation_cap = self._bounded_contracts(
                remaining_correlated_risk,
                candidate.risk_per_contract,
                contracts,
            )

            allocated_contracts = min(
                contracts,
                risk_contract_cap,
                correlation_cap,
            )

            if allocated_contracts < contracts:
                warnings.append(
                    "Allocation reduced by portfolio constraints."
                )
            if allocated_contracts <= 0:
                rejections.append(
                    "Portfolio constraints prevent allocation."
                )

            allocated_risk = (
                allocated_contracts * candidate.risk_per_contract
            )
            allocated_bp = (
                allocated_contracts
                * candidate.buying_power_per_contract
            )
            expected_profit = (
                allocated_contracts
                * candidate.maximum_profit_per_contract
                * candidate.probability_of_profit
                - allocated_contracts
                * candidate.risk_per_contract
                * (1.0 - candidate.probability_of_profit)
            )

            if allocated_contracts > 0:
                total_risk += allocated_risk
                total_bp += allocated_bp
                symbol_risk[candidate.symbol] += allocated_risk
                sector_risk[candidate.sector] += allocated_risk
                strategy_risk[candidate.strategy_name] += allocated_risk
                selected.append((candidate, allocated_contracts))

            decisions_by_id[candidate.candidate_id] = (
                AllocationDecisionProfile(
                    candidate_id=candidate.candidate_id,
                    symbol=candidate.symbol,
                    sector=candidate.sector,
                    strategy_name=candidate.strategy_name,
                    allocated_contracts=allocated_contracts,
                    allocated_risk=round(allocated_risk, 6),
                    allocated_buying_power=round(allocated_bp, 6),
                    expected_profit=round(expected_profit, 6),
                    expected_return_pct=round(
                        candidate.expected_return_pct, 6
                    ),
                    allocation_status=(
                        "ALLOCATED"
                        if allocated_contracts > 0 and not warnings
                        else "ALLOCATED_WITH_WARNINGS"
                        if allocated_contracts > 0
                        else "REJECTED"
                    ),
                    warnings=tuple(dict.fromkeys(warnings)),
                    rejection_reasons=tuple(
                        dict.fromkeys(rejections)
                    ),
                )
            )

        decisions = tuple(
            decisions_by_id[candidate.candidate_id]
            for candidate in candidates_tuple
        )

        delta = gamma = theta = vega = 0.0
        gross_directional = 0.0
        net_directional = 0.0
        total_expected_profit = 0.0
        symbol_exposure: dict[str, float] = defaultdict(float)
        sector_exposure: dict[str, float] = defaultdict(float)
        strategy_exposure: dict[str, float] = defaultdict(float)

        candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in candidates_tuple
        }
        for decision in decisions:
            candidate = candidate_by_id[decision.candidate_id]
            contracts = decision.allocated_contracts
            delta_value = candidate.delta_per_contract * contracts
            delta += delta_value
            gamma += candidate.gamma_per_contract * contracts
            theta += candidate.theta_per_contract * contracts
            vega += candidate.vega_per_contract * contracts
            gross_directional += abs(delta_value)
            net_directional += delta_value
            total_expected_profit += decision.expected_profit
            symbol_exposure[candidate.symbol] += decision.allocated_risk
            sector_exposure[candidate.sector] += decision.allocated_risk
            strategy_exposure[
                candidate.strategy_name
            ] += decision.allocated_risk

        exposure = ExposureAnalyticsProfile(
            portfolio_delta=round(delta, 6),
            portfolio_gamma=round(gamma, 6),
            portfolio_theta=round(theta, 6),
            portfolio_vega=round(vega, 6),
            gross_directional_exposure=round(
                gross_directional, 6
            ),
            net_directional_exposure=round(
                net_directional, 6
            ),
            total_risk=round(total_risk, 6),
            total_buying_power=round(total_bp, 6),
            total_expected_profit=round(
                total_expected_profit, 6
            ),
            sector_exposure={
                key: round(value, 6)
                for key, value in sorted(sector_exposure.items())
            },
            strategy_exposure={
                key: round(value, 6)
                for key, value in sorted(strategy_exposure.items())
            },
            symbol_exposure={
                key: round(value, 6)
                for key, value in sorted(symbol_exposure.items())
            },
        )

        allocated_count = sum(
            decision.allocated_contracts > 0
            for decision in decisions
        )
        unique_symbols = len(
            {
                decision.symbol
                for decision in decisions
                if decision.allocated_contracts > 0
            }
        )
        unique_sectors = len(
            {
                decision.sector
                for decision in decisions
                if decision.allocated_contracts > 0
            }
        )
        unique_strategies = len(
            {
                decision.strategy_name
                for decision in decisions
                if decision.allocated_contracts > 0
            }
        )
        breadth_target = max(1, min(5, len(candidates_tuple)))
        diversification_score = min(
            100.0,
            40.0 * unique_symbols / breadth_target
            + 30.0 * unique_sectors / breadth_target
            + 30.0 * unique_strategies / breadth_target,
        )

        max_concentration = (
            max(symbol_exposure.values(), default=0.0)
            / total_risk
            if total_risk > 0
            else 1.0
        )
        concentration_score = max(
            0.0, 100.0 * (1.0 - max_concentration)
        )
        allocated_candidates = [
            candidate_by_id[decision.candidate_id]
            for decision in decisions
            if decision.allocated_contracts > 0
        ]
        liquidity_score = (
            sum(
                candidate.liquidity_score
                for candidate in allocated_candidates
            )
            / len(allocated_candidates)
            if allocated_candidates
            else 0.0
        )
        expected_return_score = min(
            100.0,
            max(
                0.0,
                (
                    total_expected_profit
                    / max(total_risk, 1.0)
                )
                * 100.0,
            ),
        )
        capital_utilization = total_bp / account_equity
        portfolio_risk_pct = total_risk / account_equity
        health_score = (
            diversification_score * 0.30
            + concentration_score * 0.20
            + liquidity_score * 0.25
            + expected_return_score * 0.25
        )

        portfolio_warnings: list[str] = []
        portfolio_rejections: list[str] = []

        if diversification_score < self.policy.minimum_diversification_score:
            portfolio_warnings.append(
                "Portfolio diversification is below policy target."
            )
        if health_score < self.policy.minimum_portfolio_health_score:
            portfolio_warnings.append(
                "Portfolio health score is below policy target."
            )
        if portfolio_risk_pct > self.policy.maximum_portfolio_risk_pct:
            portfolio_rejections.append(
                "Portfolio risk exceeds policy."
            )
        if capital_utilization > self.policy.maximum_buying_power_pct:
            portfolio_rejections.append(
                "Buying-power utilization exceeds policy."
            )
        if allocated_count == 0:
            portfolio_rejections.append(
                "No portfolio positions were allocated."
            )

        for decision in decisions:
            portfolio_warnings.extend(decision.warnings)
            portfolio_rejections.extend(decision.rejection_reasons)

        portfolio_warnings = list(
            dict.fromkeys(portfolio_warnings)
        )
        portfolio_rejections = list(
            dict.fromkeys(portfolio_rejections)
        )

        health = PortfolioHealthProfile(
            capital_utilization_pct=round(
                capital_utilization, 6
            ),
            portfolio_risk_pct=round(portfolio_risk_pct, 6),
            remaining_buying_power=round(
                buying_power_budget - total_bp, 6
            ),
            diversification_score=round(
                diversification_score, 6
            ),
            concentration_score=round(
                concentration_score, 6
            ),
            liquidity_score=round(liquidity_score, 6),
            expected_return_score=round(
                expected_return_score, 6
            ),
            portfolio_health_score=round(health_score, 6),
            portfolio_health_grade=self._grade(health_score),
            risk_severity=self._risk_severity(
                len(portfolio_rejections),
                len(portfolio_warnings),
            ),
        )

        allowed = not portfolio_rejections and allocated_count > 0

        return PortfolioAllocationProfile(
            account_equity=round(account_equity, 6),
            candidates_evaluated=len(candidates_tuple),
            positions_allocated=allocated_count,
            sizing_profiles=sizing,
            decisions=decisions,
            exposure=exposure,
            health=health,
            allowed=allowed,
            warnings=tuple(portfolio_warnings),
            rejection_reasons=tuple(portfolio_rejections),
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 2,
                "source": "POSITION_SIZING_PORTFOLIO_ALLOCATION",
            },
        )
