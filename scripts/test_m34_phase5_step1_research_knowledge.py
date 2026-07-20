from types import SimpleNamespace

from trading_ai.research_workstation.research_knowledge import (
    ResearchKnowledgeEngine,
    research_knowledge_payload,
)


def main() -> None:
    research_case = SimpleNamespace(
        case_id="CASE-001",
        symbol="AAPL",
        strategy_name="BULL_PUT_SPREAD",
        sector="Technology",
        industry="Consumer Electronics",
        primary_thesis="Constructive bullish thesis.",
        evidence=(
            SimpleNamespace(
                title="Earnings quality",
                summary="Revenue and margins remain resilient.",
                source="internal_research",
                reliability_score=0.90,
            ),
        ),
        scenarios=(
            SimpleNamespace(
                scenario_id="BULL",
                name="Bull Case",
                probability=0.70,
                catalysts=("Positive guidance",),
            ),
        ),
    )
    scenario = SimpleNamespace(best_scenario_id="BULL")
    journal = SimpleNamespace(
        decision_action="MONITOR",
        decision_status="MONITORING",
        decision_confidence=0.80,
    )
    outcome = SimpleNamespace(
        outcome_status="PROFITABLE",
        realized_return_pct=0.14,
        decision_quality_score=0.82,
        thesis_validation=SimpleNamespace(
            validation_status="CONFIRMED"
        ),
    )
    thesis = SimpleNamespace(validation_status="CONFIRMED")
    dashboard = SimpleNamespace(institutional_score=0.84)

    engine = ResearchKnowledgeEngine()
    knowledge_case = engine.build_case(
        research_case=research_case,
        scenario_comparison=scenario,
        decision_journal=journal,
        outcome_attribution=outcome,
        thesis_validation=thesis,
        dashboard_summary=dashboard,
    )

    assert knowledge_case.case_id == "CASE-001"
    assert knowledge_case.symbol == "AAPL"
    assert knowledge_case.records
    assert knowledge_case.tags
    assert not knowledge_case.rejection_reasons

    knowledge_base = engine.build_knowledge_base(
        knowledge_base_id="KB-001",
        cases=(knowledge_case,),
    )

    assert knowledge_base.governance_status == "READY"
    assert knowledge_base.case_count == 1
    assert knowledge_base.record_count >= 4
    assert "AAPL" in knowledge_base.index.symbols
    assert "technology" in knowledge_base.index.tags
    assert "profitable" in knowledge_base.index.tags

    payload = research_knowledge_payload(knowledge_base)
    assert payload["knowledge_base_id"] == "KB-001"
    assert payload["case_count"] == 1

    print(
        "All Milestone 34 Phase 5 Step 1 research-knowledge "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
