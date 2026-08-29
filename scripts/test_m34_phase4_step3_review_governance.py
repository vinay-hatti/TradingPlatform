from types import SimpleNamespace

from trading_ai.research_workstation.decision_journal import (
    DecisionJournalEngine,
)


def main() -> None:
    research_case = SimpleNamespace(
        case_id="CASE-RISK",
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        primary_thesis="Incomplete thesis.",
    )
    scenario_comparison = SimpleNamespace(
        best_scenario_id="BASE",
        recommendation=SimpleNamespace(
            action="BUY",
            confidence=0.40,
        ),
    )

    result = DecisionJournalEngine().build(
        journal_id="JOURNAL-RISK",
        research_case=research_case,
        scenario_comparison=scenario_comparison,
        actor="Same Reviewer",
        decision_rationale="",
        primary_risks=(),
        monitoring_plan=(),
        reviews=(
            {
                "review_id": "REVIEW-SELF",
                "reviewer": "Same Reviewer",
                "review_status": "APPROVED",
                "reviewer_confidence": 0.90,
                "comments": "Self-approved.",
                "required_actions": (),
                "execution_approved": True,
            },
        ),
    )

    assert result.execution_allowed is False
    assert result.decision_status == "REJECTED"
    assert result.approval_status == "INVALID_SELF_APPROVAL"
    assert result.rejection_reasons
    assert result.warnings
    assert result.remediation_actions
    assert any(
        "Self-approval" in item
        for item in result.rejection_reasons
    )

    print(
        "Milestone 34 Phase 4 Step 3 review-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
