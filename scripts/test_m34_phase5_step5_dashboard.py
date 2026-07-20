from types import SimpleNamespace

from trading_ai.research_workstation.knowledge_dashboard import KnowledgeDashboardEngine


def main() -> None:
    dashboard = KnowledgeDashboardEngine().build(
        knowledge_base=SimpleNamespace(cases=tuple(range(10)), governance_status="READY"),
        pattern_discovery=SimpleNamespace(clusters=tuple(range(5)), governance_status="READY"),
        institutional_learning=SimpleNamespace(case_count=10, governance_status="READY"),
        analyst_performance=SimpleNamespace(
            scorecards=(SimpleNamespace(composite_score=0.80),),
            governance_status="READY",
        ),
    )
    assert dashboard.governance_status == "READY"
    assert dashboard.readiness_score >= 0.70
    assert dashboard.readiness_grade in {"A+", "A", "A-", "B+", "B", "B-"}
    assert len(dashboard.metrics) == 5
    print("Milestone 34 Phase 5 Step 5 dashboard assertions passed.")


if __name__ == "__main__":
    main()
