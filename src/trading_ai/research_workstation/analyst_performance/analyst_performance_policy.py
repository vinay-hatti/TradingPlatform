from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalystPerformancePolicy:
    minimum_cases_for_rating: int = 3
    minimum_evidence_quality: float = 0.60
    minimum_case_completeness: float = 0.80
    maximum_calibration_error: float = 0.15
    excessive_confidence_threshold: float = 0.85
    maximum_governance_failure_rate: float = 0.20
    win_weight: float = 0.25
    calibration_weight: float = 0.20
    evidence_weight: float = 0.15
    completeness_weight: float = 0.15
    institutional_weight: float = 0.15
    governance_weight: float = 0.10

    def validate(self) -> None:
        if self.minimum_cases_for_rating <= 0:
            raise ValueError("minimum_cases_for_rating must be positive.")

        for name in (
            "minimum_evidence_quality",
            "minimum_case_completeness",
            "maximum_calibration_error",
            "excessive_confidence_threshold",
            "maximum_governance_failure_rate",
            "win_weight",
            "calibration_weight",
            "evidence_weight",
            "completeness_weight",
            "institutional_weight",
            "governance_weight",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")

        total = (
            self.win_weight
            + self.calibration_weight
            + self.evidence_weight
            + self.completeness_weight
            + self.institutional_weight
            + self.governance_weight
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Analyst rating weights must sum to 1.0.")
