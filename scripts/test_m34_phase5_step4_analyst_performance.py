from types import SimpleNamespace

from trading_ai.research_workstation.analyst_performance import (
    AnalystPerformanceEngine,
)


def case(case_id, outcome, score, evidence, completeness, strategy, sector, analyst):
    return SimpleNamespace(
        case_id=case_id,
        outcome_status=outcome,
        institutional_score=score,
        evidence_quality_score=evidence,
        case_completeness_score=completeness,
        strategy_name=strategy,
        sector=sector,
        warnings=(),
        rejection_reasons=(),
        metadata={
            "analyst_id": analyst,
            "predicted_probability": score,
        },
    )


def main() -> None:
    knowledge_base = SimpleNamespace(
        cases=(
            case("C1", "PROFITABLE", 0.82, 0.90, 1.00, "BULL_PUT_SPREAD", "Technology", "ANALYST-1"),
            case("C2", "PROFITABLE", 0.80, 0.88, 0.95, "BULL_PUT_SPREAD", "Technology", "ANALYST-1"),
            case("C3", "LOSS", 0.60, 0.75, 0.90, "LONG_CALL", "Technology", "ANALYST-1"),
        )
    )

    report = AnalystPerformanceEngine().build_report(
        knowledge_base=knowledge_base
    )

    assert report.governance_status == "READY"
    assert report.analyst_count == 1
    assert report.total_case_count == 3

    scorecard = report.scorecards[0]
    assert scorecard.analyst_id == "ANALYST-1"
    assert scorecard.win_count == 2
    assert scorecard.loss_count == 1
    assert scorecard.strategy_attribution
    assert scorecard.sector_attribution
    assert scorecard.rating != "WATCHLIST"

    print(
        "Milestone 34 Phase 5 Step 4 analyst-performance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
