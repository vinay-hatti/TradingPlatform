from trading_ai.strategy_engine.decision_run_result import (
    DecisionRunResult,
)


def main():
    result = DecisionRunResult(
        decisions=[],
        selected_decisions=[],
        rejected_decisions=[],
        candidate_bundles=[],
        ranked_opportunities=[],
        portfolio_result=None,
        symbol_diagnostics=[],
        total_symbols=0,
        processed_symbols=0,
        total_candidates=0,
        accepted_candidates=0,
        rejected_candidates=0,
        selected_count=0,
        overall_readiness="NOT_READY",
        overall_action="NO_ACTION",
        valid=True,
        portfolio_risk_surface_profile=None,
        portfolio_optimization_profile=None,
        portfolio_optimization_frontier_profile=None,
        portfolio_optimization_recommendation=None,
        probability_calibration_model_family="institutional_probability_calibration",
        probability_calibration_model_version="v1",
        warnings=[],
        errors=[],
        metadata={},
    )

    assert (
        result.probability_calibration_model_family
        == "institutional_probability_calibration"
    )
    assert result.probability_calibration_model_version == "v1"

    print(
        "Phase 6 DecisionRunResult constructor regression "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
