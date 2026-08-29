from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from trading_ai.research_workstation.knowledge_dashboard import (
    KnowledgeDashboardEngine,
    write_knowledge_dashboard_html,
    write_knowledge_dashboard_json,
    write_knowledge_dashboard_summary,
)


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
    with TemporaryDirectory() as directory:
        root = Path(directory)
        html_path = write_knowledge_dashboard_html(dashboard, root / "dashboard.html")
        json_path = write_knowledge_dashboard_json(dashboard, root / "dashboard.json")
        summary_path = write_knowledge_dashboard_summary(dashboard, root / "summary.json")
        assert "Milestone 34" in html_path.read_text(encoding="utf-8")
        assert "readiness_score" in json_path.read_text(encoding="utf-8")
        assert "milestone_complete" in summary_path.read_text(encoding="utf-8")
    print("Milestone 34 Phase 5 Step 5 reporting assertions passed.")


if __name__ == "__main__":
    main()
