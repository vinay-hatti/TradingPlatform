from __future__ import annotations

from typing import Any, Iterable, Sequence

from .execution_governance_engine import ExecutionGovernanceEngine
from .execution_governance_policy import ExecutionGovernancePolicy
from .execution_governance_profile import ExecutionGovernanceProfile


class ExecutionGovernanceService:
    """Public orchestration service for execution drift governance."""

    def __init__(
        self,
        policy: ExecutionGovernancePolicy | None = None,
        engine: ExecutionGovernanceEngine | None = None,
    ):
        self.policy = policy or ExecutionGovernancePolicy()
        self.engine = engine or ExecutionGovernanceEngine(self.policy)

    def analyze(
        self,
        baseline_observations: Sequence[Any] | Iterable[Any],
        current_observations: Sequence[Any] | Iterable[Any],
        *,
        baseline_name: str = "BASELINE",
        current_name: str = "CURRENT",
        metrics: Sequence[str] | None = None,
        segment_types: Sequence[str] = ("VENUE", "BROKER"),
    ) -> ExecutionGovernanceProfile:
        return self.engine.analyze(
            baseline_observations,
            current_observations,
            baseline_name=baseline_name,
            current_name=current_name,
            metrics=metrics,
            segment_types=segment_types,
        )

    evaluate = analyze

    @staticmethod
    def attach(items: Iterable[Any], profile: ExecutionGovernanceProfile) -> None:
        for item in items or []:
            if isinstance(item, dict):
                item["execution_governance_profile"] = profile
                item["execution_governance_valid"] = profile.valid
                item["execution_governance_allowed"] = profile.allowed
                item["execution_governance_score"] = profile.governance_score
                item["execution_governance_grade"] = profile.governance_grade
                item["execution_governance_severity"] = profile.drift_severity
                metadata = item.setdefault("metadata", {})
                if isinstance(metadata, dict):
                    metadata["execution_governance_profile"] = profile
                continue

            setattr(item, "execution_governance_profile", profile)
            setattr(item, "execution_governance_valid", profile.valid)
            setattr(item, "execution_governance_allowed", profile.allowed)
            setattr(item, "execution_governance_score", profile.governance_score)
            setattr(item, "execution_governance_grade", profile.governance_grade)
            setattr(item, "execution_governance_severity", profile.drift_severity)
            metadata = getattr(item, "metadata", None)
            if not isinstance(metadata, dict):
                metadata = {}
                setattr(item, "metadata", metadata)
            metadata["execution_governance_profile"] = profile
