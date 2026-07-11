import math
from collections import Counter

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)
from trading_ai.strategy_engine.institutional_rank_breakdown import (
    InstitutionalRankBreakdown,
)
from trading_ai.strategy_engine.institutional_ranked_opportunity import (
    InstitutionalRankedOpportunity,
)
from trading_ai.strategy_engine.institutional_ranking_policy import (
    InstitutionalRankingPolicy,
)


class InstitutionalRankingEngine:
    """
    Greedy cross-symbol institutional ranking engine.

    Ranking proceeds one opportunity at a time. Each selected opportunity
    influences the diversification score of the remaining opportunities.
    """

    def __init__(
        self,
        policy: InstitutionalRankingPolicy | None = None,
    ):
        self.policy = policy or InstitutionalRankingPolicy()
        self.policy.validate()

    # ---------------------------------------------------------
    # Main ranking API
    # ---------------------------------------------------------

    def rank(
        self,
        opportunities: list[InstitutionalOpportunity],
        shortlist_size: int | None = None,
        include_rejected: bool = True,
    ) -> list[InstitutionalRankedOpportunity]:
        shortlist_size = (
            int(shortlist_size)
            if shortlist_size is not None
            else self.policy.shortlist_size
        )

        shortlist_size = max(shortlist_size, 1)

        remaining = list(opportunities)
        selected_opportunities = []
        ranked = []

        rank_number = 1

        while remaining:
            evaluated = [
                self._evaluate(
                    opportunity=opportunity,
                    selected_opportunities=selected_opportunities,
                )
                for opportunity in remaining
            ]

            evaluated.sort(
                key=self._sort_key,
                reverse=True,
            )

            best = evaluated[0]

            best.rank = rank_number

            if (
                best.allowed
                and best.ranking_score
                >= self.policy.minimum_ranking_score
                and len(selected_opportunities) < shortlist_size
            ):
                best.selected = True
                selected_opportunities.append(
                    best.opportunity
                )
            else:
                best.selected = False

            if include_rejected or best.allowed:
                ranked.append(best)
                rank_number += 1

            remaining.remove(best.opportunity)

        return ranked

    def shortlist(
        self,
        opportunities: list[InstitutionalOpportunity],
        size: int | None = None,
    ) -> list[InstitutionalRankedOpportunity]:
        size = (
            int(size)
            if size is not None
            else self.policy.shortlist_size
        )

        ranked = self.rank(
            opportunities=opportunities,
            shortlist_size=size,
            include_rejected=False,
        )

        return [
            item
            for item in ranked
            if item.selected and item.allowed
        ][:size]

    def live_candidates(
        self,
        opportunities: list[InstitutionalOpportunity],
        size: int | None = None,
    ) -> list[InstitutionalRankedOpportunity]:
        size = (
            int(size)
            if size is not None
            else self.policy.live_shortlist_size
        )

        ranked = self.rank(
            opportunities=opportunities,
            shortlist_size=max(
                size,
                self.policy.shortlist_size,
            ),
            include_rejected=False,
        )

        return [
            item
            for item in ranked
            if (
                item.allowed
                and item.selected
                and item.ranking_score
                >= self.policy.live_candidate_score
                and item.opportunity.readiness
                == "LIVE_CANDIDATE"
            )
        ][:size]

    def best(
        self,
        opportunities: list[InstitutionalOpportunity],
        allowed_only: bool = True,
    ) -> InstitutionalRankedOpportunity | None:
        ranked = self.rank(
            opportunities=opportunities,
            shortlist_size=1,
            include_rejected=not allowed_only,
        )

        candidates = [
            item
            for item in ranked
            if not allowed_only or item.allowed
        ]

        return candidates[0] if candidates else None

    # ---------------------------------------------------------
    # Opportunity evaluation
    # ---------------------------------------------------------

    def _evaluate(
        self,
        opportunity: InstitutionalOpportunity,
        selected_opportunities: list[InstitutionalOpportunity],
    ) -> InstitutionalRankedOpportunity:
        rejection_reasons = self._rejection_reasons(
            opportunity
        )

        readiness_score = self._readiness_score(
            opportunity.readiness
        )

        confidence_score = self._bound_score(
            opportunity.data_confidence_score
        )

        expected_return_score = (
            self._expected_return_score(
                opportunity.expected_return_pct
            )
        )

        probability_score = self._probability_score(
            opportunity.probability_of_profit
        )

        capital_efficiency_score = (
            self._capital_efficiency_score(
                opportunity
            )
        )

        liquidity_execution_score = (
            self._liquidity_execution_score(
                opportunity
            )
        )

        portfolio_fit_score = self._bound_score(
            opportunity.portfolio_fit_score
        )

        (
            diversification_score,
            concentration_penalty,
            diversification_reason,
        ) = self._diversification_analysis(
            opportunity=opportunity,
            selected=selected_opportunities,
        )

        component_scores = {
            "strategy_score": self._bound_score(
                opportunity.strategy_score
            ),
            "readiness": readiness_score,
            "confidence": confidence_score,
            "expected_return": expected_return_score,
            "probability": probability_score,
            "capital_efficiency": capital_efficiency_score,
            "liquidity_execution": (
                liquidity_execution_score
            ),
            "portfolio_fit": portfolio_fit_score,
            "diversification": diversification_score,
        }

        weights = self.policy.weights()

        weighted = {
            name: component_scores[name] * weights[name]
            for name in component_scores
        }

        raw_ranking_score = sum(weighted.values())

        quality_penalties, quality_warnings = (
            self._quality_penalties(opportunity)
        )

        quality_penalty = sum(
            penalty
            for _, penalty in quality_penalties
        )

        hard_penalty = (
            self.policy.maximum_total_penalty
            if rejection_reasons
            else 0.0
        )

        total_penalty = min(
            hard_penalty
            + concentration_penalty
            + quality_penalty,
            self.policy.maximum_total_penalty,
        )

        final_score = max(
            0.0,
            min(
                100.0,
                raw_ranking_score - total_penalty,
            ),
        )

        allowed = (
            not rejection_reasons
            and opportunity.allowed
            and opportunity.rank_eligible
            and opportunity.strategy_score
            >= self.policy.minimum_strategy_score
            and final_score
            >= self.policy.minimum_ranking_score
        )

        strengths = self._strengths(
            component_scores
        )

        weaknesses = self._weaknesses(
            component_scores
        )

        grade = self._grade(final_score)

        tier = self._tier(
            score=final_score,
            allowed=allowed,
        )

        action = self._action(
            opportunity=opportunity,
            score=final_score,
            allowed=allowed,
        )

        warnings = list(
            dict.fromkeys(
                list(opportunity.warnings)
                + quality_warnings
            )
        )

        breakdown = InstitutionalRankBreakdown(
            strategy_score=round(
                component_scores["strategy_score"],
                2,
            ),
            readiness_score=round(
                component_scores["readiness"],
                2,
            ),
            confidence_score=round(
                component_scores["confidence"],
                2,
            ),
            expected_return_score=round(
                component_scores["expected_return"],
                2,
            ),
            probability_score=round(
                component_scores["probability"],
                2,
            ),
            capital_efficiency_score=round(
                component_scores["capital_efficiency"],
                2,
            ),
            liquidity_execution_score=round(
                component_scores["liquidity_execution"],
                2,
            ),
            portfolio_fit_score=round(
                component_scores["portfolio_fit"],
                2,
            ),
            diversification_score=round(
                component_scores["diversification"],
                2,
            ),
            weighted_strategy_score=round(
                weighted["strategy_score"],
                4,
            ),
            weighted_readiness_score=round(
                weighted["readiness"],
                4,
            ),
            weighted_confidence_score=round(
                weighted["confidence"],
                4,
            ),
            weighted_expected_return_score=round(
                weighted["expected_return"],
                4,
            ),
            weighted_probability_score=round(
                weighted["probability"],
                4,
            ),
            weighted_capital_efficiency_score=round(
                weighted["capital_efficiency"],
                4,
            ),
            weighted_liquidity_execution_score=round(
                weighted["liquidity_execution"],
                4,
            ),
            weighted_portfolio_fit_score=round(
                weighted["portfolio_fit"],
                4,
            ),
            weighted_diversification_score=round(
                weighted["diversification"],
                4,
            ),
            raw_ranking_score=round(
                raw_ranking_score,
                2,
            ),
            hard_penalty=round(
                hard_penalty,
                2,
            ),
            concentration_penalty=round(
                concentration_penalty,
                2,
            ),
            quality_penalty=round(
                quality_penalty,
                2,
            ),
            total_penalty=round(
                total_penalty,
                2,
            ),
            final_ranking_score=round(
                final_score,
                2,
            ),
        )

        return InstitutionalRankedOpportunity(
            rank=0,
            opportunity=opportunity,
            ranking_score=round(final_score, 2),
            raw_ranking_score=round(
                raw_ranking_score,
                2,
            ),
            grade=grade,
            tier=tier,
            action=action,
            selected=False,
            allowed=allowed,
            primary_reason=self._primary_reason(
                opportunity=opportunity,
                score=final_score,
                allowed=allowed,
                rejection_reasons=rejection_reasons,
                strengths=strengths,
            ),
            diversification_reason=(
                diversification_reason
            ),
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            strengths=strengths,
            weaknesses=weaknesses,
            breakdown=breakdown,
            metadata={
                "quality_penalties": [
                    {
                        "reason": reason,
                        "value": penalty,
                    }
                    for reason, penalty
                    in quality_penalties
                ],
                "selected_symbol_count": sum(
                    1
                    for item in selected_opportunities
                    if item.symbol == opportunity.symbol
                ),
            },
        )

    # ---------------------------------------------------------
    # Hard eligibility rules
    # ---------------------------------------------------------

    def _rejection_reasons(
        self,
        opportunity: InstitutionalOpportunity,
    ) -> list[str]:
        reasons = list(
            opportunity.rejection_reasons
        )

        if (
            self.policy.reject_disallowed_opportunities
            and not opportunity.allowed
        ):
            reasons.append(
                "OPPORTUNITY_NOT_ALLOWED"
            )

        if not opportunity.rank_eligible:
            reasons.append(
                "OPPORTUNITY_NOT_RANK_ELIGIBLE"
            )

        if (
            opportunity.strategy_score
            < self.policy.minimum_strategy_score
        ):
            reasons.append(
                "STRATEGY_SCORE_BELOW_MINIMUM"
            )

        if (
            opportunity.liquidity_score
            < self.policy.minimum_liquidity_score
        ):
            reasons.append(
                "LIQUIDITY_SCORE_BELOW_MINIMUM"
            )

        if (
            opportunity.execution_score
            < self.policy.minimum_execution_score
        ):
            reasons.append(
                "EXECUTION_SCORE_BELOW_MINIMUM"
            )

        if (
            self.policy.reject_undefined_risk
            and opportunity.risk_profile
            == "UNDEFINED_RISK"
        ):
            reasons.append(
                "UNDEFINED_RISK_NOT_ALLOWED"
            )

        return list(dict.fromkeys(reasons))

    # ---------------------------------------------------------
    # Ranking components
    # ---------------------------------------------------------

    def _readiness_score(
        self,
        readiness: str,
    ) -> float:
        mapping = {
            "LIVE_CANDIDATE": 100.0,
            "PAPER_TRADING": 85.0,
            "RESEARCH_READY": 72.0,
            "RESEARCH_ONLY": 50.0,
            "WATCHLIST": 55.0,
            "INSUFFICIENT_DATA": 25.0,
            "REJECTED": 0.0,
        }

        return mapping.get(
            str(readiness or "").upper(),
            40.0,
        )

    def _expected_return_score(
        self,
        expected_return_pct: float,
    ) -> float:
        value = self._safe_float(
            expected_return_pct
        )

        if value > 1.0:
            value /= 100.0

        if value <= 0:
            return 0.0

        if value >= 0.50:
            return 100.0

        if value >= 0.30:
            return 92.0

        if value >= 0.20:
            return 84.0

        if value >= 0.15:
            return 76.0

        if value >= 0.10:
            return 68.0

        if value >= 0.05:
            return 55.0

        if value >= 0.02:
            return 40.0

        return 25.0

    def _probability_score(
        self,
        probability_of_profit: float | None,
    ) -> float:
        if probability_of_profit is None:
            return 50.0

        probability = self._safe_float(
            probability_of_profit
        )

        if probability > 1.0:
            probability /= 100.0

        return round(
            max(
                0.0,
                min(100.0, probability * 100.0),
            ),
            2,
        )

    def _capital_efficiency_score(
        self,
        opportunity: InstitutionalOpportunity,
    ) -> float:
        expected_profit = self._safe_float(
            opportunity.expected_profit
        )

        capital_required = self._safe_float(
            opportunity.capital_required
        )

        maximum_loss = self._safe_float(
            opportunity.maximum_loss
        )

        denominator = (
            capital_required
            if capital_required > 0
            else maximum_loss
        )

        if expected_profit <= 0 or denominator <= 0:
            return 40.0

        ratio = expected_profit / denominator

        if ratio >= 1.0:
            return 100.0

        if ratio >= 0.75:
            return 92.0

        if ratio >= 0.50:
            return 82.0

        if ratio >= 0.33:
            return 72.0

        if ratio >= 0.20:
            return 60.0

        if ratio >= 0.10:
            return 45.0

        return 30.0

    def _liquidity_execution_score(
        self,
        opportunity: InstitutionalOpportunity,
    ) -> float:
        liquidity = self._bound_score(
            opportunity.liquidity_score
        )

        execution = self._bound_score(
            opportunity.execution_score
        )

        return round(
            liquidity * 0.60
            + execution * 0.40,
            2,
        )

    # ---------------------------------------------------------
    # Diversification
    # ---------------------------------------------------------

    def _diversification_analysis(
        self,
        opportunity: InstitutionalOpportunity,
        selected: list[InstitutionalOpportunity],
    ) -> tuple[float, float, str]:
        if not selected:
            return (
                100.0,
                0.0,
                "No existing shortlist concentration.",
            )

        symbol_count = sum(
            1
            for item in selected
            if item.symbol == opportunity.symbol
        )

        sector_count = sum(
            1
            for item in selected
            if (
                opportunity.sector != "UNKNOWN"
                and item.sector == opportunity.sector
            )
        )

        direction_count = sum(
            1
            for item in selected
            if item.direction == opportunity.direction
        )

        strategy_count = sum(
            1
            for item in selected
            if item.strategy == opportunity.strategy
        )

        correlation_count = sum(
            1
            for item in selected
            if (
                opportunity.correlation_group
                and item.correlation_group
                == opportunity.correlation_group
            )
        )

        penalty = 0.0
        reasons = []

        if (
            symbol_count
            >= self.policy.maximum_opportunities_per_symbol
        ):
            penalty += (
                self.policy.duplicate_symbol_penalty
            )

            reasons.append(
                f"symbol {opportunity.symbol} already selected"
            )

        if (
            sector_count
            >= self.policy.maximum_opportunities_per_sector
        ):
            penalty += (
                self.policy.sector_concentration_penalty
            )

            reasons.append(
                f"sector {opportunity.sector} concentrated"
            )

        if (
            direction_count
            >= self.policy.maximum_same_direction
        ):
            penalty += (
                self.policy.direction_concentration_penalty
            )

            reasons.append(
                f"direction {opportunity.direction} concentrated"
            )

        if (
            strategy_count
            >= self.policy.maximum_same_strategy
        ):
            penalty += (
                self.policy.strategy_concentration_penalty
            )

            reasons.append(
                f"strategy {opportunity.strategy} concentrated"
            )

        if (
            opportunity.correlation_group
            and correlation_count
            >= self.policy.maximum_same_correlation_group
        ):
            penalty += (
                self.policy.correlation_concentration_penalty
            )

            reasons.append(
                "correlation group "
                f"{opportunity.correlation_group} concentrated"
            )

        score = max(
            0.0,
            100.0 - penalty * 2.0,
        )

        reason = (
            "; ".join(reasons)
            if reasons
            else "Opportunity improves shortlist diversification."
        )

        return (
            round(score, 2),
            round(penalty, 2),
            reason,
        )

    # ---------------------------------------------------------
    # Quality penalties
    # ---------------------------------------------------------

    def _quality_penalties(
        self,
        opportunity: InstitutionalOpportunity,
    ) -> tuple[list[tuple[str, float]], list[str]]:
        penalties = []
        warnings = []

        if (
            opportunity.data_confidence_score
            < self.policy.minimum_data_confidence
        ):
            penalties.append(
                (
                    "LOW_DATA_CONFIDENCE",
                    self.policy.low_confidence_penalty,
                )
            )
            warnings.append(
                "Data confidence below preferred minimum"
            )

        if (
            opportunity.liquidity_score
            < self.policy.minimum_liquidity_score
        ):
            penalties.append(
                (
                    "WEAK_LIQUIDITY",
                    self.policy.weak_liquidity_penalty,
                )
            )
            warnings.append(
                "Liquidity below institutional minimum"
            )

        if (
            opportunity.execution_score
            < self.policy.minimum_execution_score
        ):
            penalties.append(
                (
                    "WEAK_EXECUTION",
                    self.policy.weak_execution_penalty,
                )
            )
            warnings.append(
                "Execution quality below institutional minimum"
            )

        if opportunity.risk_profile == "UNDEFINED_RISK":
            penalties.append(
                (
                    "UNDEFINED_RISK",
                    self.policy.undefined_risk_penalty,
                )
            )
            warnings.append(
                "Undefined-risk opportunity"
            )

        if opportunity.complexity == "COMPLEX":
            penalties.append(
                (
                    "COMPLEX_STRATEGY",
                    self.policy.complex_strategy_penalty,
                )
            )
            warnings.append(
                "Complex multi-leg opportunity"
            )

        if opportunity.probability_of_profit is None:
            penalties.append(
                (
                    "MISSING_PROBABILITY_OF_PROFIT",
                    self.policy.missing_pop_penalty,
                )
            )
            warnings.append(
                "Probability of profit unavailable"
            )

        return penalties, warnings

    # ---------------------------------------------------------
    # Descriptive output
    # ---------------------------------------------------------

    def _strengths(
        self,
        components: dict[str, float],
    ) -> list[str]:
        return [
            self._label(name)
            for name, score in sorted(
                components.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if score >= 80
        ][:4]

    def _weaknesses(
        self,
        components: dict[str, float],
    ) -> list[str]:
        return [
            self._label(name)
            for name, score in sorted(
                components.items(),
                key=lambda item: item[1],
            )
            if score < 55
        ][:4]

    def _primary_reason(
        self,
        opportunity: InstitutionalOpportunity,
        score: float,
        allowed: bool,
        rejection_reasons: list[str],
        strengths: list[str],
    ) -> str:
        if rejection_reasons:
            return (
                f"{opportunity.symbol} "
                f"{opportunity.strategy} rejected: "
                + ", ".join(rejection_reasons)
            )

        if allowed:
            strength_text = (
                ", ".join(strengths)
                if strengths
                else "balanced institutional quality"
            )

            return (
                f"{opportunity.symbol} "
                f"{opportunity.strategy} ranked "
                f"{score:.2f} with strengths in "
                f"{strength_text}."
            )

        return (
            f"{opportunity.symbol} "
            f"{opportunity.strategy} ranked "
            f"{score:.2f}, below the minimum threshold."
        )

    def _action(
        self,
        opportunity: InstitutionalOpportunity,
        score: float,
        allowed: bool,
    ) -> str:
        if not allowed:
            return "REJECT"

        if (
            score >= self.policy.elite_candidate_score
            and opportunity.readiness == "LIVE_CANDIDATE"
        ):
            return "PRIORITY_LIVE_CANDIDATE"

        if (
            score >= self.policy.live_candidate_score
            and opportunity.readiness == "LIVE_CANDIDATE"
        ):
            return "LIVE_CANDIDATE"

        if score >= self.policy.paper_trading_score:
            return "PAPER_TRADE"

        return "WATCHLIST"

    def _tier(
        self,
        score: float,
        allowed: bool,
    ) -> str:
        if not allowed:
            return "REJECTED"

        if score >= 90:
            return "TIER_1"

        if score >= 82:
            return "TIER_2"

        if score >= 72:
            return "TIER_3"

        if score >= 60:
            return "TIER_4"

        return "RESEARCH"

    def _grade(self, score: float) -> str:
        if score >= 95:
            return "A+"

        if score >= 90:
            return "A"

        if score >= 85:
            return "A-"

        if score >= 80:
            return "B+"

        if score >= 75:
            return "B"

        if score >= 70:
            return "B-"

        if score >= 65:
            return "C+"

        if score >= 60:
            return "C"

        if score >= 50:
            return "D"

        return "F"

    def _sort_key(
        self,
        ranked: InstitutionalRankedOpportunity,
    ) -> tuple:
        opportunity = ranked.opportunity

        return (
            1 if ranked.allowed else 0,
            ranked.ranking_score,
            ranked.raw_ranking_score,
            opportunity.strategy_score,
            opportunity.liquidity_score,
            opportunity.execution_score,
            opportunity.data_confidence_score,
            opportunity.symbol,
            opportunity.strategy,
        )

    def _label(self, value: str) -> str:
        return value.replace("_", " ").title()

    def _bound_score(self, value) -> float:
        return round(
            max(
                0.0,
                min(100.0, self._safe_float(value)),
            ),
            2,
        )

    def _safe_float(
        self,
        value,
        default: float = 0.0,
    ) -> float:
        try:
            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return float(default)

            return result

        except (TypeError, ValueError):
            return float(default)

    # ---------------------------------------------------------
    # Summaries
    # ---------------------------------------------------------

    def summary(
        self,
        ranked: list[InstitutionalRankedOpportunity],
    ) -> dict:
        allowed = [
            item
            for item in ranked
            if item.allowed
        ]

        selected = [
            item
            for item in ranked
            if item.selected
        ]

        rejected = [
            item
            for item in ranked
            if not item.allowed
        ]

        actions = Counter(
            item.action
            for item in ranked
        )

        strategies = Counter(
            item.opportunity.strategy
            for item in selected
        )

        directions = Counter(
            item.opportunity.direction
            for item in selected
        )

        sectors = Counter(
            item.opportunity.sector
            for item in selected
        )

        return {
            "total_opportunities": len(ranked),
            "allowed_opportunities": len(allowed),
            "selected_opportunities": len(selected),
            "rejected_opportunities": len(rejected),
            "average_selected_score": round(
                (
                    sum(
                        item.ranking_score
                        for item in selected
                    ) / len(selected)
                )
                if selected
                else 0.0,
                2,
            ),
            "actions": dict(actions),
            "selected_strategies": dict(strategies),
            "selected_directions": dict(directions),
            "selected_sectors": dict(sectors),
        }
