from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .analyst_performance_policy import AnalystPerformancePolicy
from .analyst_performance_profile import (
    AnalystAttributionProfile,
    AnalystCalibrationProfile,
    AnalystGovernanceProfile,
    AnalystPerformanceReportProfile,
    AnalystScorecardProfile,
)


class AnalystPerformanceEngine:
    SUCCESS_OUTCOMES = {"PROFITABLE", "SUCCESS", "WIN", "CONFIRMED"}
    FAILURE_OUTCOMES = {"LOSS", "FAILED", "FAILURE", "INVALIDATED"}

    def __init__(
        self,
        policy: AnalystPerformancePolicy | None = None,
    ) -> None:
        self.policy = policy or AnalystPerformancePolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def _outcome_value(cls, case: Any) -> float:
        outcome = str(cls._get(case, "outcome_status", "UNKNOWN")).upper()
        if outcome in cls.SUCCESS_OUTCOMES:
            return 1.0
        if outcome in cls.FAILURE_OUTCOMES:
            return 0.0
        return 0.5

    def _predicted_probability(self, case: Any) -> float:
        metadata = self._get(case, "metadata", {}) or {}
        value = self._get(metadata, "predicted_probability", None)
        if value is None:
            value = self._get(case, "institutional_score", 0.5)
        return self._clamp(float(value or 0.5))

    def _analyst_id(self, case: Any) -> str:
        metadata = self._get(case, "metadata", {}) or {}
        return str(
            self._get(
                metadata,
                "analyst_id",
                self._get(metadata, "research_source", "UNASSIGNED"),
            )
            or "UNASSIGNED"
        )

    def _calibration(self, cases: tuple[Any, ...]) -> AnalystCalibrationProfile:
        predicted = [self._predicted_probability(case) for case in cases]
        realized = [self._outcome_value(case) for case in cases]

        avg_predicted = sum(predicted) / len(predicted) if predicted else 0.0
        realized_rate = sum(realized) / len(realized) if realized else 0.0
        error = abs(avg_predicted - realized_rate)
        brier = (
            sum((p - y) ** 2 for p, y in zip(predicted, realized)) / len(predicted)
            if predicted
            else 0.0
        )
        drift = avg_predicted - realized_rate

        if error <= self.policy.maximum_calibration_error / 2:
            status = "WELL_CALIBRATED"
        elif error <= self.policy.maximum_calibration_error:
            status = "ACCEPTABLE"
        else:
            status = "REQUIRES_RECALIBRATION"

        return AnalystCalibrationProfile(
            case_count=len(cases),
            average_predicted_probability=round(avg_predicted, 6),
            realized_success_rate=round(realized_rate, 6),
            calibration_error=round(error, 6),
            brier_score=round(brier, 6),
            confidence_drift=round(drift, 6),
            calibration_status=status,
        )

    def _attribution(
        self,
        cases: tuple[Any, ...],
        *,
        dimension: str,
        field_name: str,
    ) -> tuple[AnalystAttributionProfile, ...]:
        grouped: defaultdict[str, list[Any]] = defaultdict(list)
        for case in cases:
            grouped[str(self._get(case, field_name, "UNKNOWN") or "UNKNOWN")].append(case)

        result: list[AnalystAttributionProfile] = []
        for key, members in sorted(grouped.items()):
            wins = sum(1 for item in members if self._outcome_value(item) == 1.0)
            losses = sum(1 for item in members if self._outcome_value(item) == 0.0)
            result.append(
                AnalystAttributionProfile(
                    dimension=dimension,
                    key=key,
                    case_count=len(members),
                    win_count=wins,
                    loss_count=losses,
                    win_rate=round(wins / len(members), 6),
                    average_institutional_score=round(
                        sum(float(self._get(item, "institutional_score", 0.0) or 0.0) for item in members)
                        / len(members),
                        6,
                    ),
                    average_evidence_quality=round(
                        sum(float(self._get(item, "evidence_quality_score", 0.0) or 0.0) for item in members)
                        / len(members),
                        6,
                    ),
                )
            )
        return tuple(result)

    def _governance(self, cases: tuple[Any, ...]) -> AnalystGovernanceProfile:
        warning_count = sum(len(tuple(self._get(case, "warnings", ()) or ())) for case in cases)
        rejection_count = sum(len(tuple(self._get(case, "rejection_reasons", ()) or ())) for case in cases)
        missing_evidence = sum(
            1
            for case in cases
            if float(self._get(case, "evidence_quality_score", 0.0) or 0.0)
            < self.policy.minimum_evidence_quality
        )
        incomplete = sum(
            1
            for case in cases
            if float(self._get(case, "case_completeness_score", 0.0) or 0.0)
            < self.policy.minimum_case_completeness
        )
        excessive = sum(
            1
            for case in cases
            if self._predicted_probability(case) >= self.policy.excessive_confidence_threshold
            and self._outcome_value(case) < 1.0
        )

        failed_cases = sum(
            1
            for case in cases
            if tuple(self._get(case, "rejection_reasons", ()) or ())
            or float(self._get(case, "evidence_quality_score", 0.0) or 0.0)
            < self.policy.minimum_evidence_quality
            or float(self._get(case, "case_completeness_score", 0.0) or 0.0)
            < self.policy.minimum_case_completeness
        )
        failure_rate = failed_cases / len(cases) if cases else 0.0

        findings: list[str] = []
        if missing_evidence:
            findings.append(f"{missing_evidence} case(s) below evidence-quality threshold.")
        if incomplete:
            findings.append(f"{incomplete} case(s) below completeness threshold.")
        if excessive:
            findings.append(f"{excessive} excessive-confidence case(s) detected.")
        if rejection_count:
            findings.append(f"{rejection_count} rejection reason(s) recorded.")
        if not findings:
            findings.append("No material governance findings.")

        return AnalystGovernanceProfile(
            case_count=len(cases),
            warning_count=warning_count,
            rejection_count=rejection_count,
            governance_failure_rate=round(failure_rate, 6),
            missing_evidence_count=missing_evidence,
            incomplete_case_count=incomplete,
            excessive_confidence_count=excessive,
            findings=tuple(findings),
        )

    @staticmethod
    def _rating(score: float, case_count: int, minimum_cases: int) -> str:
        if case_count < minimum_cases:
            return "WATCHLIST"
        if score >= 0.93:
            return "A+"
        if score >= 0.88:
            return "A"
        if score >= 0.84:
            return "A-"
        if score >= 0.80:
            return "B+"
        if score >= 0.75:
            return "B"
        if score >= 0.70:
            return "B-"
        if score >= 0.60:
            return "C"
        return "WATCHLIST"

    def build_scorecard(
        self,
        *,
        analyst_id: str,
        cases: Iterable[Any],
    ) -> AnalystScorecardProfile:
        case_list = tuple(cases)
        calibration = self._calibration(case_list)
        governance = self._governance(case_list)

        wins = sum(1 for case in case_list if self._outcome_value(case) == 1.0)
        losses = sum(1 for case in case_list if self._outcome_value(case) == 0.0)
        neutral = len(case_list) - wins - losses
        win_rate = wins / len(case_list) if case_list else 0.0

        avg_institutional = (
            sum(float(self._get(case, "institutional_score", 0.0) or 0.0) for case in case_list)
            / len(case_list)
            if case_list
            else 0.0
        )
        avg_evidence = (
            sum(float(self._get(case, "evidence_quality_score", 0.0) or 0.0) for case in case_list)
            / len(case_list)
            if case_list
            else 0.0
        )
        avg_completeness = (
            sum(float(self._get(case, "case_completeness_score", 0.0) or 0.0) for case in case_list)
            / len(case_list)
            if case_list
            else 0.0
        )

        calibration_component = 1.0 - min(
            1.0,
            calibration.calibration_error / max(self.policy.maximum_calibration_error, 1e-9),
        )
        governance_component = 1.0 - governance.governance_failure_rate

        composite = (
            self.policy.win_weight * win_rate
            + self.policy.calibration_weight * calibration_component
            + self.policy.evidence_weight * avg_evidence
            + self.policy.completeness_weight * avg_completeness
            + self.policy.institutional_weight * avg_institutional
            + self.policy.governance_weight * governance_component
        )
        composite = self._clamp(composite)

        strengths: list[str] = []
        improvements: list[str] = []

        if win_rate >= 0.70:
            strengths.append("Strong realized success rate.")
        else:
            improvements.append("Improve realized success consistency.")
        if calibration.calibration_status == "WELL_CALIBRATED":
            strengths.append("Confidence estimates are well calibrated.")
        elif calibration.calibration_status == "REQUIRES_RECALIBRATION":
            improvements.append("Recalibrate confidence estimates.")
        if avg_evidence >= self.policy.minimum_evidence_quality:
            strengths.append("Evidence quality meets policy.")
        else:
            improvements.append("Improve evidence quality.")
        if avg_completeness >= self.policy.minimum_case_completeness:
            strengths.append("Research completeness meets policy.")
        else:
            improvements.append("Improve research completeness.")
        if governance.governance_failure_rate > self.policy.maximum_governance_failure_rate:
            improvements.append("Reduce repeated governance failures.")

        return AnalystScorecardProfile(
            analyst_id=analyst_id,
            case_count=len(case_list),
            win_count=wins,
            loss_count=losses,
            neutral_count=neutral,
            win_rate=round(win_rate, 6),
            average_institutional_score=round(avg_institutional, 6),
            average_evidence_quality=round(avg_evidence, 6),
            average_case_completeness=round(avg_completeness, 6),
            calibration=calibration,
            governance=governance,
            strategy_attribution=self._attribution(
                case_list,
                dimension="STRATEGY",
                field_name="strategy_name",
            ),
            sector_attribution=self._attribution(
                case_list,
                dimension="SECTOR",
                field_name="sector",
            ),
            composite_score=round(composite, 6),
            rating=self._rating(
                composite,
                len(case_list),
                self.policy.minimum_cases_for_rating,
            ),
            strengths=tuple(strengths),
            improvement_areas=tuple(improvements),
            metadata={
                "milestone": 34,
                "phase": 5,
                "step": 4,
            },
        )

    def build_report(
        self,
        *,
        knowledge_base: Any,
        report_id: str = "M34-PHASE5-ANALYST-PERFORMANCE-001",
        generated_at: datetime | None = None,
    ) -> AnalystPerformanceReportProfile:
        cases = tuple(self._get(knowledge_base, "cases", ()) or ())
        grouped: defaultdict[str, list[Any]] = defaultdict(list)
        for case in cases:
            grouped[self._analyst_id(case)].append(case)

        scorecards = tuple(
            self.build_scorecard(analyst_id=analyst_id, cases=members)
            for analyst_id, members in sorted(grouped.items())
        )

        warnings: list[str] = []
        if not cases:
            warnings.append("No research cases were available.")
        if cases and all(card.rating == "WATCHLIST" for card in scorecards):
            warnings.append("No analyst has sufficient history for a stable rating.")

        governance_status = "READY" if cases else "INSUFFICIENT_HISTORY"

        return AnalystPerformanceReportProfile(
            report_id=report_id,
            generated_at=generated_at or datetime.now(timezone.utc),
            analyst_count=len(scorecards),
            total_case_count=len(cases),
            scorecards=scorecards,
            governance_status=governance_status,
            warnings=tuple(warnings),
            metadata={
                "milestone": 34,
                "phase": 5,
                "step": 4,
            },
        )
