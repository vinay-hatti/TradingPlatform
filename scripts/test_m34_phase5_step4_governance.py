from types import SimpleNamespace

from trading_ai.research_workstation.analyst_performance import (
    AnalystPerformanceEngine,
)


def main() -> None:
    empty_report = AnalystPerformanceEngine().build_report(
        knowledge_base=SimpleNamespace(cases=())
    )
    assert empty_report.governance_status == "INSUFFICIENT_HISTORY"
    assert empty_report.warnings

    weak_case = SimpleNamespace(
        outcome_status="LOSS",
        institutional_score=0.95,
        evidence_quality_score=0.20,
        case_completeness_score=0.40,
        strategy_name="LONG_CALL",
        sector="Unknown",
        warnings=("Evidence weak.",),
        rejection_reasons=("Case incomplete.",),
        metadata={"predicted_probability": 0.95},
    )

    scorecard = AnalystPerformanceEngine().build_scorecard(
        analyst_id="WATCHLIST",
        cases=(weak_case,),
    )

    assert scorecard.rating == "WATCHLIST"
    assert scorecard.governance.missing_evidence_count == 1
    assert scorecard.governance.incomplete_case_count == 1
    assert scorecard.governance.excessive_confidence_count == 1
    assert scorecard.improvement_areas

    print(
        "Milestone 34 Phase 5 Step 4 governance assertions passed."
    )


if __name__ == "__main__":
    main()
