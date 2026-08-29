from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N

from trading_ai.research_workstation.dashboard import (
    ResearchDashboardEngine,
    write_dashboard_summary,
    write_research_dashboard_html,
    write_research_dashboard_json,
)


def main() -> None:
    case = N(
        case_id="C",
        symbol="AAPL",
        strategy_name="S",
        primary_thesis="T",
        evidence=(N(reliability_score=0.9),),
    )
    comparison = N(
        best_scenario_id="B",
        recommendation=N(action="MONITOR", confidence=0.7),
    )
    journal = N(
        journal_id="J",
        case_id="C",
        decision_confidence=0.7,
        decision_status="MONITORING",
        approval_status="APPROVED",
        decision_rationale="R",
        primary_risks=("R",),
        monitoring_plan=("M",),
    )
    thesis = N(
        validation_status="CONFIRMED",
        confirmation_score=0.8,
        thesis_summary="T",
    )
    attribution = N(
        case_id="C",
        journal_id="J",
        forecast_accuracy=N(overall_forecast_accuracy=0.8),
        scenario_calibration=N(calibration_score=0.8),
        thesis_validation=thesis,
        decision_quality_score=0.8,
        decision_quality_grade="B",
        outcome_status="PROFITABLE",
        positive_factors=(),
        warnings=(),
        remediation_actions=(),
    )

    result = ResearchDashboardEngine().build(
        dashboard_id="D",
        research_case=case,
        scenario_comparison=comparison,
        decision_journal=journal,
        outcome_attribution=attribution,
        thesis_validation=N(case_id="C", thesis_validation=thesis),
    )

    with TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        json_path = write_research_dashboard_json(
            result, output_dir / "dashboard.json"
        )
        html_path = write_research_dashboard_html(
            result, output_dir / "dashboard.html"
        )
        summary_path = write_dashboard_summary(
            result, output_dir / "summary.json"
        )

        assert "Institutional Research Dashboard" in html_path.read_text(
            encoding="utf-8"
        )
        assert json_path.exists()
        assert html_path.exists()
        assert summary_path.exists()

    print(
        "Milestone 34 Phase 4 Step 5 dashboard-reporting "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
