from types import SimpleNamespace

from trading_ai.research_workstation.research_knowledge import (
    ResearchKnowledgeEngine,
)


def main() -> None:
    engine = ResearchKnowledgeEngine()

    incomplete_case = SimpleNamespace(
        case_id="",
        symbol="",
        strategy_name="LONG_CALL",
        primary_thesis="",
        evidence=(),
        scenarios=(),
    )

    result = engine.build_case(
        research_case=incomplete_case,
        scenario_comparison=None,
        decision_journal=None,
    )

    assert result.rejection_reasons
    assert result.remediation_actions
    assert result.warnings
    assert result.case_completeness_score < 0.80

    base = engine.build_knowledge_base(
        knowledge_base_id="KB-GOVERNANCE",
        cases=(result,),
    )
    assert base.governance_status == "REJECTED"
    assert base.rejection_reasons

    print(
        "Milestone 34 Phase 5 Step 1 knowledge-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
