from __future__ import annotations

from itertools import combinations
from math import isfinite
from typing import Any, Mapping

from .scenario_comparison_policy import ScenarioComparisonPolicy
from .scenario_comparison_profile import (
    ExpectedValueBreakdownProfile,
    RecommendationProfile,
    ScenarioComparisonProfile,
    ScenarioDeltaProfile,
    ScenarioRankingProfile,
    SensitivityDimensionProfile,
)


class ScenarioComparisonEngine:
    def __init__(
        self,
        policy: ScenarioComparisonPolicy | None = None,
    ) -> None:
        self.policy = policy or ScenarioComparisonPolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

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
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _normalize(
        self,
        value: float,
        lower: float,
        upper: float,
        *,
        invert: bool = False,
    ) -> float:
        if upper <= lower:
            score = 50.0
        else:
            score = ((value - lower) / (upper - lower)) * 100.0
        score = self._clamp(score, 0.0, 100.0)
        return 100.0 - score if invert else score

    def _sensitivity_classification(
        self,
        relative_change: float,
    ) -> str:
        magnitude = abs(relative_change)
        if magnitude <= self.policy.low_sensitivity_threshold:
            return "LOW"
        if magnitude <= self.policy.moderate_sensitivity_threshold:
            return "MODERATE"
        if magnitude <= self.policy.high_sensitivity_threshold:
            return "HIGH"
        return "CRITICAL"

    def _recommendation(
        self,
        *,
        score: float,
        confidence: float,
        weighted_return: float,
        weighted_drawdown: float,
        warnings: tuple[str, ...],
        rejections: tuple[str, ...],
        rankings: tuple[ScenarioRankingProfile, ...],
        sensitivities: tuple[SensitivityDimensionProfile, ...],
    ) -> RecommendationProfile:
        primary_drivers: list[str] = []
        key_risks: list[str] = []
        monitoring: list[str] = []

        if weighted_return > 0:
            primary_drivers.append(
                "Probability-weighted expected return is positive."
            )
        if rankings:
            primary_drivers.append(
                f"Top-ranked scenario is {rankings[0].scenario_name}."
            )
        if weighted_drawdown <= 0.10:
            primary_drivers.append(
                "Probability-weighted drawdown remains controlled."
            )
        else:
            key_risks.append(
                "Probability-weighted drawdown is elevated."
            )

        critical = [
            item for item in sensitivities
            if item.classification == "CRITICAL"
        ]
        high = [
            item for item in sensitivities
            if item.classification == "HIGH"
        ]
        if critical:
            key_risks.append(
                "One or more assumptions have critical sensitivity."
            )
        elif high:
            key_risks.append(
                "One or more assumptions have high sensitivity."
            )

        for item in sensitivities:
            if item.classification in {"HIGH", "CRITICAL"}:
                monitoring.append(
                    f"Monitor {item.dimension} closely."
                )

        if rejections:
            action = "REJECT"
            rationale = (
                "Scenario comparison failed governance requirements."
            )
        elif score >= self.policy.minimum_score_for_strong_buy and (
            confidence
            >= self.policy.minimum_confidence_for_strong_buy
        ) and weighted_return > 0:
            action = "STRONG_BUY"
            rationale = (
                "High-quality scenario distribution with strong "
                "confidence and positive expected value."
            )
        elif score >= self.policy.minimum_score_for_buy and (
            confidence >= self.policy.minimum_confidence_for_buy
        ) and weighted_return > 0:
            action = "BUY"
            rationale = (
                "Scenario distribution supports a positive risk-adjusted "
                "decision."
            )
        elif weighted_return > 0 and score >= 60:
            action = "OPPORTUNISTIC_BUY"
            rationale = (
                "Expected value is positive but conviction or robustness "
                "is below full-buy thresholds."
            )
        elif score >= 50:
            action = "MONITOR"
            rationale = (
                "Scenario evidence is mixed and requires continued review."
            )
        elif weighted_return > self.policy.negative_expected_value_threshold:
            action = "WAIT"
            rationale = (
                "Expected value is marginal relative to scenario risk."
            )
        elif score > self.policy.reject_score_threshold:
            action = "REDUCE"
            rationale = (
                "Scenario risk exceeds the quality of the expected return."
            )
        else:
            action = "REJECT"
            rationale = (
                "Scenario comparison is not investable under policy."
            )

        key_risks.extend(warnings)

        return RecommendationProfile(
            action=action,
            confidence=round(confidence, 6),
            recommendation_score=round(score, 6),
            rationale=rationale,
            primary_drivers=tuple(dict.fromkeys(primary_drivers)),
            key_risks=tuple(dict.fromkeys(key_risks)),
            monitoring_requirements=tuple(
                dict.fromkeys(monitoring)
            ),
        )

    def compare(
        self,
        *,
        research_case: Any,
        sensitivity_inputs: Mapping[str, Any] | None = None,
    ) -> ScenarioComparisonProfile:
        scenarios = tuple(
            self._get(research_case, "scenarios", ()) or ()
        )
        case_id = str(
            self._get(research_case, "case_id", "UNKNOWN")
        )
        symbol = str(
            self._get(research_case, "symbol", "UNKNOWN")
        )
        strategy_name = str(
            self._get(research_case, "strategy_name", "UNKNOWN")
        )
        confidence = float(
            self._get(research_case, "confidence_score", 0.0)
        )

        warnings: list[str] = []
        rejections: list[str] = []
        remediation: list[str] = []
        positives: list[str] = []

        if len(scenarios) < self.policy.minimum_scenarios:
            rejections.append(
                "Scenario count is below comparison policy minimum."
            )
            remediation.append(
                "Add additional scenarios before comparison."
            )
        elif len(scenarios) > self.policy.maximum_scenarios:
            warnings.append(
                "Scenario count exceeds comparison policy maximum."
            )
            remediation.append(
                "Consolidate overlapping scenarios."
            )
        else:
            positives.append("Scenario count within policy")

        probability_total = round(
            sum(
                float(self._get(item, "probability", 0.0))
                for item in scenarios
            ),
            10,
        )
        if abs(probability_total - 1.0) > (
            self.policy.probability_tolerance
        ):
            rejections.append(
                "Scenario probabilities are not normalized to 1.0."
            )
            remediation.append(
                "Normalize scenario probabilities before comparison."
            )
        else:
            positives.append("Scenario probabilities normalized")

        returns = [
            float(self._get(item, "expected_return_pct", 0.0))
            for item in scenarios
        ] or [0.0]
        volatilities = [
            float(
                self._get(item, "expected_volatility_pct", 0.0)
            )
            for item in scenarios
        ] or [0.0]
        drawdowns = [
            float(
                self._get(item, "expected_drawdown_pct", 0.0)
            )
            for item in scenarios
        ] or [0.0]
        probabilities = [
            float(self._get(item, "probability", 0.0))
            for item in scenarios
        ] or [0.0]

        rankings_raw = []
        breakdown = []
        for item in scenarios:
            scenario_id = str(
                self._get(item, "scenario_id", "UNKNOWN")
            )
            scenario_name = str(
                self._get(item, "name", scenario_id)
            )
            scenario_type = str(
                self._get(item, "scenario_type", "ALTERNATIVE")
            )
            probability = float(
                self._get(item, "probability", 0.0)
            )
            expected_return = float(
                self._get(item, "expected_return_pct", 0.0)
            )
            volatility = float(
                self._get(item, "expected_volatility_pct", 0.0)
            )
            drawdown = float(
                self._get(item, "expected_drawdown_pct", 0.0)
            )

            return_score = self._normalize(
                expected_return, min(returns), max(returns)
            )
            volatility_score = self._normalize(
                volatility,
                min(volatilities),
                max(volatilities),
                invert=True,
            )
            drawdown_score = self._normalize(
                drawdown,
                min(drawdowns),
                max(drawdowns),
                invert=True,
            )
            confidence_score = confidence * 100.0
            probability_score = probability * 100.0

            composite = (
                return_score * self.policy.return_weight
                + volatility_score * self.policy.volatility_weight
                + drawdown_score * self.policy.drawdown_weight
                + confidence_score * self.policy.confidence_weight
                + probability_score * self.policy.probability_weight
            )
            confidence_adjusted = composite * confidence

            rankings_raw.append(
                (
                    composite,
                    ScenarioRankingProfile(
                        rank=0,
                        scenario_id=scenario_id,
                        scenario_name=scenario_name,
                        scenario_type=scenario_type,
                        composite_score=round(composite, 6),
                        expected_return_pct=expected_return,
                        expected_volatility_pct=volatility,
                        expected_drawdown_pct=drawdown,
                        probability=probability,
                        confidence_adjusted_score=round(
                            confidence_adjusted, 6
                        ),
                        rank_reason=(
                            "Ranked using return, volatility, drawdown, "
                            "confidence, and probability."
                        ),
                    ),
                )
            )

            breakdown.append(
                ExpectedValueBreakdownProfile(
                    scenario_id=scenario_id,
                    scenario_name=scenario_name,
                    probability=probability,
                    expected_return_pct=expected_return,
                    weighted_return_pct=round(
                        probability * expected_return, 6
                    ),
                    weighted_volatility_pct=round(
                        probability * volatility, 6
                    ),
                    weighted_drawdown_pct=round(
                        probability * drawdown, 6
                    ),
                )
            )

        rankings_sorted = sorted(
            rankings_raw,
            key=lambda value: (
                value[0],
                value[1].expected_return_pct,
                -value[1].expected_drawdown_pct,
            ),
            reverse=True,
        )
        rankings = tuple(
            ScenarioRankingProfile(
                rank=index,
                scenario_id=item.scenario_id,
                scenario_name=item.scenario_name,
                scenario_type=item.scenario_type,
                composite_score=item.composite_score,
                expected_return_pct=item.expected_return_pct,
                expected_volatility_pct=item.expected_volatility_pct,
                expected_drawdown_pct=item.expected_drawdown_pct,
                probability=item.probability,
                confidence_adjusted_score=(
                    item.confidence_adjusted_score
                ),
                rank_reason=item.rank_reason,
            )
            for index, (_, item) in enumerate(
                rankings_sorted, start=1
            )
        )

        scenario_deltas = []
        for left, right in combinations(scenarios, 2):
            left_return = float(
                self._get(left, "expected_return_pct", 0.0)
            )
            right_return = float(
                self._get(right, "expected_return_pct", 0.0)
            )
            left_volatility = float(
                self._get(left, "expected_volatility_pct", 0.0)
            )
            right_volatility = float(
                self._get(right, "expected_volatility_pct", 0.0)
            )
            left_drawdown = float(
                self._get(left, "expected_drawdown_pct", 0.0)
            )
            right_drawdown = float(
                self._get(right, "expected_drawdown_pct", 0.0)
            )
            left_probability = float(
                self._get(left, "probability", 0.0)
            )
            right_probability = float(
                self._get(right, "probability", 0.0)
            )

            left_dominates = (
                left_return >= right_return
                and left_volatility <= right_volatility
                and left_drawdown <= right_drawdown
                and (
                    left_return > right_return
                    or left_volatility < right_volatility
                    or left_drawdown < right_drawdown
                )
            )
            right_dominates = (
                right_return >= left_return
                and right_volatility <= left_volatility
                and right_drawdown <= left_drawdown
                and (
                    right_return > left_return
                    or right_volatility < left_volatility
                    or right_drawdown < left_drawdown
                )
            )
            if left_dominates:
                dominance = "LEFT_DOMINATES"
            elif right_dominates:
                dominance = "RIGHT_DOMINATES"
            else:
                dominance = "NON_DOMINATED"

            scenario_deltas.append(
                ScenarioDeltaProfile(
                    left_scenario_id=str(
                        self._get(left, "scenario_id", "UNKNOWN")
                    ),
                    right_scenario_id=str(
                        self._get(right, "scenario_id", "UNKNOWN")
                    ),
                    return_delta_pct=round(
                        left_return - right_return, 6
                    ),
                    volatility_delta_pct=round(
                        left_volatility - right_volatility, 6
                    ),
                    drawdown_delta_pct=round(
                        left_drawdown - right_drawdown, 6
                    ),
                    probability_delta=round(
                        left_probability - right_probability, 6
                    ),
                    dominance=dominance,
                )
            )

        weighted_return = round(
            sum(item.weighted_return_pct for item in breakdown), 6
        )
        weighted_volatility = round(
            sum(
                item.weighted_volatility_pct
                for item in breakdown
            ),
            6,
        )
        weighted_drawdown = round(
            sum(
                item.weighted_drawdown_pct
                for item in breakdown
            ),
            6,
        )

        sensitivity_profiles = []
        for dimension, raw in dict(
            sensitivity_inputs or {}
        ).items():
            if isinstance(raw, Mapping):
                baseline = float(raw.get("baseline", 0.0))
                stressed = float(raw.get("stressed", baseline))
                notes = str(
                    raw.get(
                        "notes",
                        "Sensitivity evaluated from supplied stress input.",
                    )
                )
            else:
                baseline = 0.0
                stressed = float(raw)
                notes = "Sensitivity evaluated from scalar stress input."

            absolute_change = stressed - baseline
            denominator = abs(baseline)
            relative_change = (
                absolute_change / denominator
                if denominator > 1e-12
                else (0.0 if absolute_change == 0.0 else 1.0)
            )
            classification = self._sensitivity_classification(
                relative_change
            )
            score_impact = {
                "LOW": -1.0,
                "MODERATE": -3.0,
                "HIGH": -7.0,
                "CRITICAL": -12.0,
            }[classification]

            sensitivity_profiles.append(
                SensitivityDimensionProfile(
                    dimension=str(dimension),
                    baseline_value=baseline,
                    stressed_value=stressed,
                    absolute_change=round(absolute_change, 6),
                    relative_change=round(relative_change, 6),
                    classification=classification,
                    score_impact=score_impact,
                    notes=notes,
                )
            )

        if any(
            item.classification == "CRITICAL"
            for item in sensitivity_profiles
        ):
            warnings.append(
                "Critical scenario sensitivity is present."
            )
            remediation.append(
                "Reduce exposure or strengthen scenario assumptions."
            )
        elif any(
            item.classification == "HIGH"
            for item in sensitivity_profiles
        ):
            warnings.append(
                "High scenario sensitivity is present."
            )
            remediation.append(
                "Monitor high-sensitivity dimensions."
            )
        else:
            positives.append("Sensitivity remains controlled")

        average_rank_score = (
            sum(item.composite_score for item in rankings)
            / len(rankings)
            if rankings
            else 0.0
        )
        sensitivity_penalty = abs(
            sum(item.score_impact for item in sensitivity_profiles)
        )
        comparison_score = self._clamp(
            average_rank_score - sensitivity_penalty, 0.0, 100.0
        )

        if not isfinite(comparison_score):
            rejections.append("Comparison score is non-finite.")
            remediation.append(
                "Review scenario inputs for invalid numeric values."
            )
            comparison_score = 0.0

        if weighted_return > 0:
            positives.append("Weighted expected return is positive")
        else:
            warnings.append(
                "Weighted expected return is non-positive."
            )
            remediation.append(
                "Reassess scenario probabilities and payoff assumptions."
            )

        status = (
            "REJECTED"
            if rejections
            else "REVIEW_REQUIRED"
            if warnings
            else "READY"
        )

        recommendation = self._recommendation(
            score=comparison_score,
            confidence=confidence,
            weighted_return=weighted_return,
            weighted_drawdown=weighted_drawdown,
            warnings=tuple(dict.fromkeys(warnings)),
            rejections=tuple(dict.fromkeys(rejections)),
            rankings=rankings,
            sensitivities=tuple(sensitivity_profiles),
        )

        return ScenarioComparisonProfile(
            case_id=case_id,
            symbol=symbol,
            strategy_name=strategy_name,
            status=status,
            comparison_score=round(comparison_score, 6),
            comparison_grade=self._grade(comparison_score),
            probability_total=probability_total,
            weighted_expected_return_pct=weighted_return,
            weighted_expected_volatility_pct=weighted_volatility,
            weighted_expected_drawdown_pct=weighted_drawdown,
            best_scenario_id=(
                rankings[0].scenario_id if rankings else None
            ),
            worst_scenario_id=(
                rankings[-1].scenario_id if rankings else None
            ),
            rankings=rankings,
            expected_value_breakdown=tuple(breakdown),
            scenario_deltas=tuple(scenario_deltas),
            sensitivities=tuple(sensitivity_profiles),
            recommendation=recommendation,
            positive_factors=tuple(dict.fromkeys(positives)),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            remediation_actions=tuple(
                dict.fromkeys(remediation)
            ),
            metadata={
                "milestone": 34,
                "phase": 4,
                "step": 2,
                "source": "SCENARIO_COMPARISON_SENSITIVITY",
            },
        )
