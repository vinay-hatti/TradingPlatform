from __future__ import annotations

from typing import Iterable

from trading_ai.research_workstation.analysis.candidate_analysis_profile import (
    CandidateAnalysisProfile,
)
from trading_ai.research_workstation.analytics.payoff_profile import (
    PayoffAnalysisProfile,
)

from .institutional_explainability_policy import (
    InstitutionalExplainabilityPolicy,
)
from .institutional_explainability_profile import (
    DecisionFactorProfile,
    InstitutionalExplainabilityProfile,
    ScenarioAnalysisProfile,
    ScenarioComparisonProfile,
    ScenarioDefinitionProfile,
    ScenarioOutcomeProfile,
)


class InstitutionalExplainabilityEngine:
    def __init__(
        self,
        policy: InstitutionalExplainabilityPolicy | None = None,
    ):
        self.policy = policy or InstitutionalExplainabilityPolicy()
        self.policy.validate()

    @staticmethod
    def _bound(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _materiality(
        contribution: float,
        *,
        strong_threshold: float,
        material_threshold: float,
    ) -> str:
        absolute = abs(contribution)
        if absolute >= strong_threshold:
            return "PRIMARY"
        if absolute >= material_threshold:
            return "MATERIAL"
        return "SUPPORTING"

    @staticmethod
    def _direction(score: float) -> str:
        if score >= 65.0:
            return "POSITIVE"
        if score < 45.0:
            return "NEGATIVE"
        return "NEUTRAL"

    @staticmethod
    def _nearest_payoff(
        payoff: PayoffAnalysisProfile,
        price: float,
    ) -> float:
        point = min(
            payoff.payoff_points,
            key=lambda item: abs(item.underlying_price - price),
        )
        return float(point.profit_loss)

    def _factor(
        self,
        *,
        name: str,
        category: str,
        score: float,
        weight: float,
        rationale: str,
    ) -> DecisionFactorProfile:
        normalized = self._bound(score)
        contribution = round(normalized * weight, 6)
        return DecisionFactorProfile(
            name=name,
            category=category,
            raw_score=normalized,
            weight=weight,
            weighted_contribution=contribution,
            direction=self._direction(normalized),
            materiality=self._materiality(
                contribution,
                strong_threshold=self.policy.strong_positive_threshold,
                material_threshold=self.policy.material_threshold,
            ),
            rationale=rationale,
        )

    def _factors(
        self,
        candidate: CandidateAnalysisProfile,
        payoff: PayoffAnalysisProfile,
    ) -> tuple[DecisionFactorProfile, ...]:
        payoff_quality = (
            self._bound(payoff.return_on_risk * 100.0)
            if payoff.maximum_loss not in {None, 0}
            else 50.0
        )
        reward_risk_quality = self._bound(
            candidate.risk.reward_risk_ratio * 25.0
        )

        return (
            self._factor(
                name="Technical Structure",
                category="TECHNICAL",
                score=candidate.technical.technical_score,
                weight=self.policy.technical_weight,
                rationale=(
                    f"Trend {candidate.technical.trend_score:.2f}, "
                    f"momentum {candidate.technical.momentum_score:.2f}, "
                    f"regime {candidate.technical.regime_score:.2f}."
                ),
            ),
            self._factor(
                name="Market Liquidity",
                category="LIQUIDITY",
                score=candidate.liquidity.liquidity_score,
                weight=self.policy.liquidity_weight,
                rationale=(
                    f"Liquidity grade "
                    f"{candidate.liquidity.market_quality}; spread "
                    f"{candidate.liquidity.spread_pct:.4f}."
                ),
            ),
            self._factor(
                name="Volatility Opportunity",
                category="VOLATILITY",
                score=candidate.volatility.volatility_score,
                weight=self.policy.volatility_weight,
                rationale=(
                    f"IV rank {candidate.volatility.iv_rank:.2f}; "
                    f"ATR {candidate.volatility.atr_pct:.2f}%."
                ),
            ),
            self._factor(
                name="Institutional Decision",
                category="INSTITUTIONAL",
                score=candidate.institutional.institutional_score,
                weight=self.policy.institutional_weight,
                rationale=(
                    f"Strategy {candidate.institutional.strategy}; "
                    f"calibrated probability "
                    f"{candidate.institutional.calibrated_probability:.4f}; "
                    f"tail grade "
                    f"{candidate.institutional.tail_risk_grade}."
                ),
            ),
            self._factor(
                name="Risk and Reward",
                category="RISK_REWARD",
                score=reward_risk_quality,
                weight=self.policy.risk_reward_weight,
                rationale=(
                    f"Reward/risk "
                    f"{candidate.risk.reward_risk_ratio:.4f}; "
                    f"risk grade {candidate.risk.risk_grade}."
                ),
            ),
            self._factor(
                name="Payoff Efficiency",
                category="PAYOFF",
                score=payoff_quality,
                weight=self.policy.payoff_weight,
                rationale=(
                    f"Return on risk {payoff.return_on_risk:.4f}; "
                    f"maximum profit {payoff.maximum_profit}; "
                    f"maximum loss {payoff.maximum_loss}."
                ),
            ),
        )

    def default_scenarios(
        self,
    ) -> tuple[ScenarioDefinitionProfile, ...]:
        return (
            ScenarioDefinitionProfile(
                name="BASE",
                description="No price, volatility, or time shock.",
                probability_weight=0.30,
            ),
            ScenarioDefinitionProfile(
                name="BULLISH_SHOCK",
                description="Underlying rises by policy shock.",
                price_shock_pct=self.policy.bullish_price_shock_pct,
                probability_weight=0.15,
            ),
            ScenarioDefinitionProfile(
                name="BEARISH_SHOCK",
                description="Underlying falls by policy shock.",
                price_shock_pct=self.policy.bearish_price_shock_pct,
                probability_weight=0.15,
            ),
            ScenarioDefinitionProfile(
                name="VOLATILITY_EXPANSION",
                description="Implied volatility expands.",
                volatility_shock_points=(
                    self.policy.volatility_expansion_points
                ),
                probability_weight=0.15,
            ),
            ScenarioDefinitionProfile(
                name="VOLATILITY_CONTRACTION",
                description="Implied volatility contracts.",
                volatility_shock_points=(
                    self.policy.volatility_contraction_points
                ),
                probability_weight=0.10,
            ),
            ScenarioDefinitionProfile(
                name="TIME_DECAY",
                description="Position advances through time.",
                days_elapsed=self.policy.time_decay_days,
                probability_weight=0.15,
            ),
        )

    def _scenario_outcome(
        self,
        definition: ScenarioDefinitionProfile,
        payoff: PayoffAnalysisProfile,
    ) -> ScenarioOutcomeProfile:
        base_price = payoff.underlying_price
        shocked_price = base_price * (
            1.0 + definition.price_shock_pct
        )
        price_change = shocked_price - base_price

        expiry_payoff = self._nearest_payoff(payoff, shocked_price)
        delta_effect = payoff.greeks.total_delta * price_change
        gamma_effect = (
            0.5
            * payoff.greeks.total_gamma
            * price_change
            * price_change
        )
        theta_effect = (
            payoff.greeks.total_theta * definition.days_elapsed
        )
        vega_effect = (
            payoff.greeks.total_vega
            * definition.volatility_shock_points
        )
        total_greeks_effect = (
            delta_effect + gamma_effect + theta_effect + vega_effect
        )

        projected = expiry_payoff + theta_effect + vega_effect
        max_loss = payoff.maximum_loss
        if max_loss and max_loss > 0:
            projected_ror = projected / max_loss
            loss_fraction = max(0.0, -projected / max_loss)
        else:
            projected_ror = 0.0
            loss_fraction = 1.0 if projected < 0 else 0.0

        warnings: list[str] = []
        if loss_fraction >= 0.75:
            risk_level = "HIGH"
            warnings.append(
                "Projected loss consumes at least 75% of maximum risk"
            )
        elif loss_fraction >= 0.35:
            risk_level = "MODERATE"
            warnings.append(
                "Projected loss consumes a material share of maximum risk"
            )
        else:
            risk_level = "LOW"

        if definition.volatility_shock_points > 0 and (
            payoff.greeks.total_vega < 0
        ):
            warnings.append(
                "Volatility expansion conflicts with short-vega exposure"
            )
        if definition.days_elapsed > 0 and payoff.greeks.total_theta < 0:
            warnings.append(
                "Time passage conflicts with negative-theta exposure"
            )

        return ScenarioOutcomeProfile(
            name=definition.name,
            underlying_price=round(shocked_price, 6),
            projected_profit_loss=round(projected, 6),
            projected_return_on_risk=round(projected_ror, 6),
            delta_effect=round(delta_effect, 6),
            gamma_effect=round(gamma_effect, 6),
            theta_effect=round(theta_effect, 6),
            vega_effect=round(vega_effect, 6),
            total_greeks_effect=round(total_greeks_effect, 6),
            risk_level=risk_level,
            favorable=projected > 0,
            warnings=tuple(warnings),
        )

    def _scenario_analysis(
        self,
        payoff: PayoffAnalysisProfile,
        scenarios: Iterable[ScenarioDefinitionProfile] | None,
    ) -> ScenarioAnalysisProfile:
        definitions = tuple(scenarios or self.default_scenarios())
        if not definitions:
            raise ValueError("At least one scenario is required.")

        outcomes = tuple(
            self._scenario_outcome(definition, payoff)
            for definition in definitions
        )
        best = max(outcomes, key=lambda item: item.projected_profit_loss)
        worst = min(outcomes, key=lambda item: item.projected_profit_loss)

        total_probability = sum(
            max(0.0, item.probability_weight)
            for item in definitions
        )
        weighted = 0.0
        if total_probability > 0:
            weighted = sum(
                outcome.projected_profit_loss
                * max(0.0, definition.probability_weight)
                / total_probability
                for definition, outcome in zip(definitions, outcomes)
            )

        comparison = ScenarioComparisonProfile(
            best_scenario=best.name,
            worst_scenario=worst.name,
            best_projected_profit_loss=best.projected_profit_loss,
            worst_projected_profit_loss=worst.projected_profit_loss,
            payoff_range=round(
                best.projected_profit_loss
                - worst.projected_profit_loss,
                6,
            ),
            favorable_scenario_count=sum(
                1 for item in outcomes if item.favorable
            ),
            adverse_scenario_count=sum(
                1 for item in outcomes if not item.favorable
            ),
            high_risk_scenario_count=sum(
                1 for item in outcomes if item.risk_level == "HIGH"
            ),
            probability_weighted_profit_loss=round(weighted, 6),
        )
        return ScenarioAnalysisProfile(
            definitions=definitions,
            outcomes=outcomes,
            comparison=comparison,
        )

    def analyze(
        self,
        *,
        candidate: CandidateAnalysisProfile,
        payoff: PayoffAnalysisProfile,
        scenarios: Iterable[ScenarioDefinitionProfile] | None = None,
    ) -> InstitutionalExplainabilityProfile:
        factors = self._factors(candidate, payoff)
        score = round(
            sum(item.weighted_contribution for item in factors),
            6,
        )
        scenario_analysis = self._scenario_analysis(payoff, scenarios)

        high_risk_count = (
            scenario_analysis.comparison.high_risk_scenario_count
        )
        if (
            score >= self.policy.approval_threshold
            and high_risk_count
            <= self.policy.maximum_high_risk_scenarios
        ):
            approval_status = "APPROVED"
        elif score >= self.policy.watch_threshold:
            approval_status = "WATCH"
        else:
            approval_status = "REJECTED"

        primary_drivers = tuple(
            item.name
            for item in sorted(
                (
                    factor
                    for factor in factors
                    if factor.direction == "POSITIVE"
                ),
                key=lambda factor: -factor.weighted_contribution,
            )[:3]
        )
        primary_risks = list(
            factor.name
            for factor in factors
            if (
                factor.direction == "NEGATIVE"
                or (
                    factor.materiality == "PRIMARY"
                    and factor.raw_score < 65.0
                )
            )
        )

        if (
            scenario_analysis.comparison.worst_projected_profit_loss < 0
            and "Payoff Efficiency" not in primary_risks
        ):
            primary_risks.append("Payoff Efficiency")

        if high_risk_count:
            primary_risks.append(
                f"{high_risk_count} high-risk scenario(s)"
            )

        warnings = list(candidate.warnings)
        warnings.extend(payoff.warnings)
        for outcome in scenario_analysis.outcomes:
            warnings.extend(outcome.warnings)
        warnings = list(dict.fromkeys(warnings))

        strategy = (
            candidate.institutional.strategy
            if candidate.institutional.strategy != "UNAVAILABLE"
            else payoff.strategy_name
        )
        summary = (
            f"{candidate.symbol} / {strategy} is {approval_status.lower()} "
            f"with an explainability score of {score:.2f}. "
            f"Best scenario: "
            f"{scenario_analysis.comparison.best_scenario}; "
            f"worst scenario: "
            f"{scenario_analysis.comparison.worst_scenario}."
        )

        audit = tuple(
            [
                (
                    f"{factor.name}: raw={factor.raw_score:.2f}, "
                    f"weight={factor.weight:.2f}, "
                    f"contribution="
                    f"{factor.weighted_contribution:.2f}, "
                    f"direction={factor.direction}."
                )
                for factor in factors
            ]
            + [
                (
                    f"Scenario {outcome.name}: "
                    f"price={outcome.underlying_price:.2f}, "
                    f"P/L={outcome.projected_profit_loss:.2f}, "
                    f"risk={outcome.risk_level}."
                )
                for outcome in scenario_analysis.outcomes
            ]
        )

        return InstitutionalExplainabilityProfile(
            symbol=candidate.symbol,
            strategy=strategy,
            recommendation=candidate.explanation.recommendation,
            approval_status=approval_status,
            explainability_score=score,
            confidence=candidate.explanation.confidence,
            factor_contributions=factors,
            primary_drivers=primary_drivers,
            primary_risks=tuple(primary_risks),
            scenario_analysis=scenario_analysis,
            decision_summary=summary,
            audit_narrative=audit,
            warnings=tuple(warnings),
            metadata={
                "source": "M34_PHASE2_STEP4_EXPLAINABILITY",
                "policy_version": "1.0",
                "candidate_readiness": (
                    candidate.explanation.readiness
                ),
            },
        )
