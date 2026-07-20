from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchKnowledgePolicy:
    minimum_case_completeness: float = 0.80
    minimum_evidence_quality: float = 0.50
    minimum_tag_confidence: float = 0.50
    maximum_tags_per_case: int = 25
    maximum_records_per_case: int = 100
    require_case_id: bool = True
    require_symbol: bool = True
    require_primary_thesis: bool = True
    require_outcome_attribution: bool = False
    allow_duplicate_case_ids: bool = False

    def validate(self) -> None:
        for name in (
            "minimum_case_completeness",
            "minimum_evidence_quality",
            "minimum_tag_confidence",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")

        for name in (
            "maximum_tags_per_case",
            "maximum_records_per_case",
        ):
            value = int(getattr(self, name))
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
