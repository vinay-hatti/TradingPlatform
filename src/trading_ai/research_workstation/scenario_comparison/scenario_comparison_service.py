from __future__ import annotations

from typing import Any, Mapping

from .scenario_comparison_engine import ScenarioComparisonEngine
from .scenario_comparison_profile import ScenarioComparisonProfile


class ScenarioComparisonService:
    def __init__(
        self,
        engine: ScenarioComparisonEngine | None = None,
    ) -> None:
        self.engine = engine or ScenarioComparisonEngine()

    def compare(
        self,
        *,
        research_case: Any,
        sensitivity_inputs: Mapping[str, Any] | None = None,
    ) -> ScenarioComparisonProfile:
        return self.engine.compare(
            research_case=research_case,
            sensitivity_inputs=sensitivity_inputs,
        )
