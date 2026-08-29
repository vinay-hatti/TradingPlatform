from types import SimpleNamespace

from trading_ai.research_workstation.analyst_performance import (
    AnalystPerformanceEngine,
)


def main() -> None:
    cases = (
        SimpleNamespace(
            outcome_status="PROFITABLE",
            institutional_score=0.80,
            evidence_quality_score=0.90,
            case_completeness_score=1.00,
            strategy_name="BULL_PUT_SPREAD",
            sector="Technology",
            warnings=(),
            rejection_reasons=(),
            metadata={"predicted_probability": 0.80},
        ),
        SimpleNamespace(
            outcome_status="LOSS",
            institutional_score=0.20,
            evidence_quality_score=0.90,
            case_completeness_score=1.00,
            strategy_name="LONG_PUT",
            sector="Technology",
            warnings=(),
            rejection_reasons=(),
            metadata={"predicted_probability": 0.20},
        ),
        SimpleNamespace(
            outcome_status="PROFITABLE",
            institutional_score=0.75,
            evidence_quality_score=0.90,
            case_completeness_score=1.00,
            strategy_name="BULL_PUT_SPREAD",
            sector="Technology",
            warnings=(),
            rejection_reasons=(),
            metadata={"predicted_probability": 0.75},
        ),
    )

    scorecard = AnalystPerformanceEngine().build_scorecard(
        analyst_id="CALIBRATED",
        cases=cases,
    )

    assert scorecard.calibration.case_count == 3
    assert 0.0 <= scorecard.calibration.brier_score <= 1.0
    assert scorecard.calibration.calibration_status in {
        "WELL_CALIBRATED",
        "ACCEPTABLE",
        "REQUIRES_RECALIBRATION",
    }
    assert scorecard.composite_score > 0.0

    print(
        "Milestone 34 Phase 5 Step 4 calibration assertions passed."
    )


if __name__ == "__main__":
    main()
