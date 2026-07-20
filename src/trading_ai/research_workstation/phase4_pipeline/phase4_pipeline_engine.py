from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from trading_ai.research_workstation.research_cases import (
    ResearchCaseEngine,
    write_research_case_report,
)
from trading_ai.research_workstation.scenario_comparison import (
    ScenarioComparisonEngine,
    write_scenario_comparison_report,
)

from .phase4_pipeline_profile import Phase4PipelineResultProfile
from .phase4_pipeline_serialization import write_phase4_pipeline_report


class Phase4PipelineEngine:
    def __init__(
        self,
        *,
        research_case_engine: ResearchCaseEngine | None = None,
        scenario_comparison_engine: (
            ScenarioComparisonEngine | None
        ) = None,
    ) -> None:
        self.research_case_engine = (
            research_case_engine or ResearchCaseEngine()
        )
        self.scenario_comparison_engine = (
            scenario_comparison_engine
            or ScenarioComparisonEngine()
        )

    def run(
        self,
        *,
        manifest: Mapping[str, Any],
        output_directory: str | Path,
    ) -> Phase4PipelineResultProfile:
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        case_input = dict(manifest.get("research_case", {}))
        sensitivity_inputs = dict(
            manifest.get("sensitivity_inputs", {})
        )

        research_case = self.research_case_engine.build(
            case_id=str(case_input.get("case_id", "CASE-001")),
            symbol=str(case_input.get("symbol", "")).upper(),
            strategy_name=str(
                case_input.get("strategy_name", "")
            ).upper(),
            title=str(case_input.get("title", "")),
            primary_thesis=str(
                case_input.get("primary_thesis", "")
            ),
            time_horizon=str(
                case_input.get("time_horizon", "")
            ),
            review_date=case_input.get("review_date"),
            confidence_score=float(
                case_input.get("confidence_score", 0.0)
            ),
            scenarios=tuple(
                case_input.get("scenarios", ()) or ()
            ),
            evidence=tuple(
                case_input.get("evidence", ()) or ()
            ),
            assumptions=tuple(
                case_input.get("assumptions", ()) or ()
            ),
            metadata={
                "source": "PHASE4_PIPELINE",
                **dict(case_input.get("metadata", {}) or {}),
            },
        )
        research_case_report = write_research_case_report(
            research_case,
            output_dir / "research_case.json",
        )

        scenario_comparison = (
            self.scenario_comparison_engine.compare(
                research_case=research_case,
                sensitivity_inputs=sensitivity_inputs,
            )
        )
        scenario_comparison_report = (
            write_scenario_comparison_report(
                scenario_comparison,
                output_dir / "scenario_comparison.json",
            )
        )

        provisional = Phase4PipelineResultProfile(
            case_id=research_case.case_id,
            symbol=research_case.symbol,
            strategy_name=research_case.strategy_name,
            output_directory=output_dir,
            research_case_report=research_case_report,
            scenario_comparison_report=(
                scenario_comparison_report
            ),
            pipeline_report=output_dir / "phase4_pipeline.json",
            research_case_status=research_case.status,
            scenario_comparison_status=(
                scenario_comparison.status
            ),
            recommendation_action=(
                scenario_comparison.recommendation.action
            ),
            metadata={
                "milestone": 34,
                "phase": 4,
                "steps_completed": (1, 2),
                "source": "PHASE4_STEPS1_2_PIPELINE",
            },
        )
        pipeline_report = write_phase4_pipeline_report(
            provisional,
            provisional.pipeline_report,
        )

        return Phase4PipelineResultProfile(
            case_id=provisional.case_id,
            symbol=provisional.symbol,
            strategy_name=provisional.strategy_name,
            output_directory=provisional.output_directory,
            research_case_report=(
                provisional.research_case_report
            ),
            scenario_comparison_report=(
                provisional.scenario_comparison_report
            ),
            pipeline_report=pipeline_report,
            research_case_status=(
                provisional.research_case_status
            ),
            scenario_comparison_status=(
                provisional.scenario_comparison_status
            ),
            recommendation_action=(
                provisional.recommendation_action
            ),
            metadata=provisional.metadata,
        )
