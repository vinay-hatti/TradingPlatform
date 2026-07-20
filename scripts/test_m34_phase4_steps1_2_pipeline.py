from pathlib import Path
from tempfile import TemporaryDirectory

from run_m34_phase4_pipeline import demo_manifest

from trading_ai.research_workstation.phase4_pipeline import (
    Phase4PipelineEngine,
)


def main() -> None:
    with TemporaryDirectory() as tmp:
        result = Phase4PipelineEngine().run(
            manifest=demo_manifest(
                case_id="CASE-PIPELINE",
                symbol="AAPL",
                strategy_name="BULL_PUT_SPREAD",
            ),
            output_directory=tmp,
        )

        required = (
            result.research_case_report,
            result.scenario_comparison_report,
            result.pipeline_report,
        )
        assert all(Path(path).exists() for path in required)
        assert result.case_id == "CASE-PIPELINE"
        assert result.symbol == "AAPL"
        assert result.strategy_name == "BULL_PUT_SPREAD"
        assert result.research_case_status == "READY"
        assert result.scenario_comparison_status in {
            "READY",
            "REVIEW_REQUIRED",
        }
        assert result.recommendation_action in {
            "STRONG_BUY",
            "BUY",
            "OPPORTUNISTIC_BUY",
            "MONITOR",
            "WAIT",
            "REDUCE",
            "REJECT",
        }

    print(
        "All Milestone 34 Phase 4 Steps 1-2 pipeline "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
