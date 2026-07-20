from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionJournalPolicy:
    minimum_decision_confidence: float = 0.50
    minimum_reviewer_confidence: float = 0.60
    require_decision_rationale: bool = True
    require_primary_risk: bool = True
    require_monitoring_plan: bool = True
    require_review_for_execution: bool = True
    require_thesis_revision_reason: bool = True
    allow_self_approval: bool = False
    maximum_open_review_age_days: int = 7

    def validate(self) -> None:
        for name in (
            "minimum_decision_confidence",
            "minimum_reviewer_confidence",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.maximum_open_review_age_days <= 0:
            raise ValueError(
                "maximum_open_review_age_days must be positive."
            )
