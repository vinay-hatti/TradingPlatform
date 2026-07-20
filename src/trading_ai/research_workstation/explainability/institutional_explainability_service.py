from __future__ import annotations

from typing import Iterable

from trading_ai.research_workstation.analysis.candidate_analysis_profile import (
    CandidateAnalysisProfile,
)
from trading_ai.research_workstation.analytics.payoff_profile import (
    PayoffAnalysisProfile,
)

from .institutional_explainability_engine import (
    InstitutionalExplainabilityEngine,
)
from .institutional_explainability_profile import (
    InstitutionalExplainabilityProfile,
    ScenarioDefinitionProfile,
)


class InstitutionalExplainabilityService:
    def __init__(
        self,
        engine: InstitutionalExplainabilityEngine | None = None,
    ):
        self.engine = engine or InstitutionalExplainabilityEngine()

    def explain(
        self,
        *,
        candidate: CandidateAnalysisProfile,
        payoff: PayoffAnalysisProfile,
        scenarios: Iterable[ScenarioDefinitionProfile] | None = None,
    ) -> InstitutionalExplainabilityProfile:
        return self.engine.analyze(
            candidate=candidate,
            payoff=payoff,
            scenarios=scenarios,
        )
