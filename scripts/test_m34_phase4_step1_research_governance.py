from trading_ai.research_workstation.research_cases import (
    ResearchCaseEngine,
)


def main() -> None:
    profile = ResearchCaseEngine().build(
        case_id="CASE-RISK",
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        title="Incomplete research case",
        primary_thesis="",
        time_horizon="",
        review_date="2026-07-26",
        confidence_score=0.20,
        scenarios=(
            {
                "scenario_type": "BASE",
                "probability": 0.40,
                "expected_return_pct": 0.05,
                "expected_volatility_pct": 0.25,
                "expected_drawdown_pct": 0.10,
                "expected_holding_days": 10,
                "thesis": "Incomplete.",
                "catalysts": (),
                "risks": (),
                "invalidation_conditions": (),
                "recommended_action": "REVIEW",
            },
        ),
        evidence=(),
        assumptions=(),
    )

    assert profile.status == "REJECTED"
    assert profile.research_grade == "F"
    assert profile.rejection_reasons
    assert profile.warnings
    assert profile.remediation_actions
    assert profile.scenario_probability_total == 0.4
    assert "Primary thesis is required." in profile.rejection_reasons
    assert any(
        "Missing required scenario types" in reason
        for reason in profile.rejection_reasons
    )

    print(
        "Milestone 34 Phase 4 Step 1 research-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
