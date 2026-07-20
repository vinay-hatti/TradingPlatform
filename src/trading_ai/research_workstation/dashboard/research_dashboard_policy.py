from dataclasses import dataclass

@dataclass(frozen=True)
class ResearchDashboardPolicy:
    minimum_completeness_score: float = 0.90
    minimum_institutional_score: float = 0.60
    require_consistent_case_ids: bool = True
    require_consistent_journal_link: bool = True
    required_artifacts: tuple[str, ...] = (
        "research_case", "scenario_comparison", "decision_journal",
        "outcome_attribution", "thesis_validation",
    )

    def validate(self) -> None:
        for name in ("minimum_completeness_score", "minimum_institutional_score"):
            value=float(getattr(self,name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if not self.required_artifacts:
            raise ValueError("required_artifacts cannot be empty.")
