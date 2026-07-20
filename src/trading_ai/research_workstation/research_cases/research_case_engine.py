from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from .research_case_policy import ResearchCasePolicy
from .research_case_profile import (
    ResearchAssumptionProfile,
    ResearchCaseProfile,
    ResearchEvidenceProfile,
    ResearchScenarioProfile,
)


class ResearchCaseEngine:
    def __init__(
        self,
        policy: ResearchCasePolicy | None = None,
    ) -> None:
        self.policy = policy or ResearchCasePolicy()
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
    def _date(value: date | str) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(value)

    @staticmethod
    def _datetime(value: datetime | str | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _scenario(
        self,
        source: Any,
        index: int,
    ) -> ResearchScenarioProfile:
        return ResearchScenarioProfile(
            scenario_id=str(
                self._get(source, "scenario_id", f"SCENARIO-{index}")
            ),
            name=str(self._get(source, "name", f"Scenario {index}")),
            scenario_type=str(
                self._get(source, "scenario_type", "ALTERNATIVE")
            ).upper(),
            probability=float(
                self._get(source, "probability", 0.0)
            ),
            expected_return_pct=float(
                self._get(source, "expected_return_pct", 0.0)
            ),
            expected_volatility_pct=float(
                self._get(source, "expected_volatility_pct", 0.0)
            ),
            expected_drawdown_pct=float(
                self._get(source, "expected_drawdown_pct", 0.0)
            ),
            expected_holding_days=int(
                self._get(source, "expected_holding_days", 0)
            ),
            thesis=str(self._get(source, "thesis", "")),
            catalysts=tuple(
                str(value)
                for value in self._get(source, "catalysts", ()) or ()
            ),
            risks=tuple(
                str(value)
                for value in self._get(source, "risks", ()) or ()
            ),
            invalidation_conditions=tuple(
                str(value)
                for value in self._get(
                    source, "invalidation_conditions", ()
                ) or ()
            ),
            recommended_action=str(
                self._get(source, "recommended_action", "REVIEW")
            ).upper(),
        )

    def _evidence(
        self,
        source: Any,
        index: int,
    ) -> ResearchEvidenceProfile:
        return ResearchEvidenceProfile(
            evidence_id=str(
                self._get(source, "evidence_id", f"EVIDENCE-{index}")
            ),
            category=str(
                self._get(source, "category", "GENERAL")
            ).upper(),
            description=str(
                self._get(source, "description", "")
            ),
            source=str(self._get(source, "source", "UNKNOWN")),
            observed_at=self._datetime(
                self._get(source, "observed_at", None)
            ),
            reliability_score=float(
                self._get(source, "reliability_score", 0.0)
            ),
            supports_thesis=bool(
                self._get(source, "supports_thesis", False)
            ),
            notes=self._get(source, "notes", None),
        )

    def _assumption(
        self,
        source: Any,
        index: int,
    ) -> ResearchAssumptionProfile:
        return ResearchAssumptionProfile(
            assumption_id=str(
                self._get(
                    source, "assumption_id", f"ASSUMPTION-{index}"
                )
            ),
            description=str(
                self._get(source, "description", "")
            ),
            importance=str(
                self._get(source, "importance", "MEDIUM")
            ).upper(),
            confidence=float(
                self._get(source, "confidence", 0.0)
            ),
            validation_method=str(
                self._get(source, "validation_method", "")
            ),
            invalidation_condition=str(
                self._get(source, "invalidation_condition", "")
            ),
        )

    def build(
        self,
        *,
        case_id: str,
        symbol: str,
        strategy_name: str,
        title: str,
        primary_thesis: str,
        time_horizon: str,
        review_date: date | str,
        confidence_score: float,
        scenarios: Iterable[Any],
        evidence: Iterable[Any],
        assumptions: Iterable[Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> ResearchCaseProfile:
        scenario_profiles = tuple(
            self._scenario(item, index)
            for index, item in enumerate(scenarios, start=1)
        )
        evidence_profiles = tuple(
            self._evidence(item, index)
            for index, item in enumerate(evidence, start=1)
        )
        assumption_profiles = tuple(
            self._assumption(item, index)
            for index, item in enumerate(assumptions, start=1)
        )

        warnings: list[str] = []
        rejections: list[str] = []
        remediation: list[str] = []
        positives: list[str] = []

        if (
            self.policy.require_primary_thesis
            and not primary_thesis.strip()
        ):
            rejections.append("Primary thesis is required.")
            remediation.append("Document the primary investment thesis.")
        else:
            positives.append("Primary thesis documented")

        if (
            self.policy.require_time_horizon
            and not time_horizon.strip()
        ):
            rejections.append("Research time horizon is required.")
            remediation.append("Define the research time horizon.")
        else:
            positives.append("Time horizon documented")

        if len(scenario_profiles) < self.policy.minimum_scenarios:
            rejections.append(
                "Research case has fewer scenarios than policy requires."
            )
            remediation.append(
                "Add base, bull, and bear scenarios."
            )
        elif len(scenario_profiles) > self.policy.maximum_scenarios:
            warnings.append(
                "Research case contains more scenarios than recommended."
            )
            remediation.append(
                "Consolidate low-value or overlapping scenarios."
            )
        else:
            positives.append("Scenario count within policy")

        scenario_types = {
            item.scenario_type for item in scenario_profiles
        }
        required = []
        if self.policy.require_base_case:
            required.append("BASE")
        if self.policy.require_bull_case:
            required.append("BULL")
        if self.policy.require_bear_case:
            required.append("BEAR")
        missing = [
            item for item in required if item not in scenario_types
        ]
        if missing:
            rejections.append(
                "Missing required scenario types: "
                + ", ".join(missing)
            )
            remediation.append(
                "Add all required institutional scenario types."
            )
        else:
            positives.append("Required scenarios present")

        probability_total = round(
            sum(item.probability for item in scenario_profiles),
            10,
        )
        if not (
            self.policy.minimum_total_scenario_probability
            <= probability_total
            <= self.policy.maximum_total_scenario_probability
        ):
            rejections.append(
                "Scenario probabilities must sum to 1.0."
            )
            remediation.append(
                "Normalize scenario probabilities."
            )
        else:
            positives.append("Scenario probabilities normalized")

        base_cases = [
            item for item in scenario_profiles
            if item.scenario_type == "BASE"
        ]
        if base_cases:
            base_probability = base_cases[0].probability
            if not (
                self.policy.minimum_base_case_probability
                <= base_probability
                <= self.policy.maximum_base_case_probability
            ):
                warnings.append(
                    "Base-case probability is outside policy range."
                )
                remediation.append(
                    "Review the base-case probability assignment."
                )

        if len(evidence_profiles) < self.policy.minimum_evidence_items:
            rejections.append(
                "Insufficient evidence is attached to the research case."
            )
            remediation.append(
                "Attach at least one reliable evidence item."
            )
        else:
            positives.append("Evidence attached")

        if len(assumption_profiles) < self.policy.minimum_assumptions:
            rejections.append(
                "Insufficient assumptions are documented."
            )
            remediation.append(
                "Document material assumptions and invalidation tests."
            )
        else:
            positives.append("Assumptions documented")

        if self.policy.require_invalidation_condition:
            missing_scenario_invalidations = [
                item.name
                for item in scenario_profiles
                if not item.invalidation_conditions
            ]
            missing_assumption_invalidations = [
                item.assumption_id
                for item in assumption_profiles
                if not item.invalidation_condition.strip()
            ]
            if (
                missing_scenario_invalidations
                or missing_assumption_invalidations
            ):
                warnings.append(
                    "One or more invalidation conditions are missing."
                )
                remediation.append(
                    "Add explicit invalidation conditions."
                )
            else:
                positives.append("Invalidation conditions documented")

        confidence = max(0.0, min(1.0, float(confidence_score)))
        if confidence < self.policy.minimum_case_confidence:
            warnings.append(
                "Research confidence is below policy threshold."
            )
            remediation.append(
                "Strengthen evidence or reduce conviction."
            )
        else:
            positives.append("Research confidence meets policy")

        weak_evidence = [
            item
            for item in evidence_profiles
            if item.reliability_score < 0.50
        ]
        if weak_evidence:
            warnings.append(
                "One or more evidence items have low reliability."
            )
            remediation.append(
                "Replace or corroborate low-reliability evidence."
            )

        probability_weighted_return = sum(
            item.probability * item.expected_return_pct
            for item in scenario_profiles
        )
        probability_weighted_volatility = sum(
            item.probability * item.expected_volatility_pct
            for item in scenario_profiles
        )
        probability_weighted_drawdown = sum(
            item.probability * item.expected_drawdown_pct
            for item in scenario_profiles
        )

        score = 100.0
        score -= 15.0 * len(rejections)
        score -= 5.0 * len(warnings)
        score = max(0.0, round(score, 6))

        if rejections:
            status = "REJECTED"
        elif warnings:
            status = "REVIEW_REQUIRED"
        else:
            status = "READY"

        return ResearchCaseProfile(
            case_id=case_id,
            symbol=symbol.upper(),
            strategy_name=strategy_name.upper(),
            title=title,
            primary_thesis=primary_thesis,
            time_horizon=time_horizon,
            review_date=self._date(review_date),
            status=status,
            confidence_score=round(confidence, 6),
            research_score=score,
            research_grade=self._grade(score),
            scenario_probability_total=probability_total,
            expected_return_pct=round(
                probability_weighted_return, 6
            ),
            expected_volatility_pct=round(
                probability_weighted_volatility, 6
            ),
            expected_drawdown_pct=round(
                probability_weighted_drawdown, 6
            ),
            scenarios=scenario_profiles,
            evidence=evidence_profiles,
            assumptions=assumption_profiles,
            positive_factors=tuple(dict.fromkeys(positives)),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            remediation_actions=tuple(
                dict.fromkeys(remediation)
            ),
            metadata={
                "milestone": 34,
                "phase": 4,
                "step": 1,
                "source": "RESEARCH_CASE_SCENARIO_WORKSPACE",
                **dict(metadata or {}),
            },
        )
