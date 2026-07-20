from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeDashboardPolicy:
    knowledge_weight: float = 0.20
    pattern_weight: float = 0.20
    learning_weight: float = 0.20
    analyst_weight: float = 0.20
    governance_weight: float = 0.20
    ready_threshold: float = 0.70

    def validate(self) -> None:
        values = (
            self.knowledge_weight,
            self.pattern_weight,
            self.learning_weight,
            self.analyst_weight,
            self.governance_weight,
        )
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("Dashboard weights must be between 0 and 1.")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("Dashboard weights must sum to 1.0.")
        if not 0.0 <= self.ready_threshold <= 1.0:
            raise ValueError("ready_threshold must be between 0 and 1.")
