from types import SimpleNamespace

from trading_ai.research_workstation.decision_journal import (
    DecisionJournalEngine,
    decision_journal_payload,
)


def main() -> None:
    research_case = SimpleNamespace(
        case_id="CASE-001",
        symbol="AAPL",
        strategy_name="BULL_PUT_SPREAD",
        primary_thesis="Constructive bullish thesis.",
    )
    scenario_comparison = SimpleNamespace(
        best_scenario_id="BULL",
        recommendation=SimpleNamespace(
            action="BUY",
            confidence=0.82,
        ),
    )

    result = DecisionJournalEngine().build(
        journal_id="JOURNAL-001",
        research_case=research_case,
        scenario_comparison=scenario_comparison,
        actor="Primary Analyst",
        decision_rationale=(
            "Positive expected value and controlled downside."
        ),
        primary_risks=(
            "Volatility expansion",
            "Support failure",
        ),
        monitoring_plan=(
            "Review probabilities daily",
            "Monitor liquidity",
        ),
        reviews=(
            {
                "review_id": "REVIEW-001",
                "reviewer": "Independent Reviewer",
                "review_status": "APPROVED",
                "reviewer_confidence": 0.85,
                "comments": "Approved.",
                "required_actions": (),
                "execution_approved": True,
            },
        ),
        thesis_revisions=(
            {
                "revision_id": "REV-001",
                "previous_thesis": (
                    "Constructive bullish thesis."
                ),
                "revised_thesis": (
                    "Constructive bullish thesis with tighter "
                    "risk controls."
                ),
                "revision_reason": (
                    "Volatility increased modestly."
                ),
                "author": "Primary Analyst",
                "material_change": False,
            },
        ),
    )

    assert result.decision_action == "BUY"
    assert result.approval_status == "APPROVED"
    assert result.execution_allowed is True
    assert result.decision_status == "APPROVED_FOR_EXECUTION"
    assert result.selected_scenario_id == "BULL"
    assert len(result.reviews) == 1
    assert len(result.thesis_revisions) == 1
    assert len(result.entries) == 3
    assert not result.rejection_reasons
    assert result.current_thesis.endswith("risk controls.")

    payload = decision_journal_payload(result)
    assert payload["journal_id"] == "JOURNAL-001"
    assert payload["execution_allowed"] is True

    print(
        "All Milestone 34 Phase 4 Step 3 decision-journal "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
