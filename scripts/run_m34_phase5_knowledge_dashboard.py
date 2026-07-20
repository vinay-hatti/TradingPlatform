from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.knowledge_dashboard import (
    KnowledgeDashboardEngine,
    write_knowledge_dashboard_html,
    write_knowledge_dashboard_json,
    write_knowledge_dashboard_summary,
)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_namespace(item) for item in value)
    return value


def _load(path: str) -> Any:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Required report not found: {source}")
    return _namespace(json.loads(source.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Milestone 34 Phase 5 knowledge dashboard.")
    parser.add_argument("--knowledge-base-json", default="reports/m34/phase5/research_knowledge_base.json")
    parser.add_argument("--pattern-discovery-json", default="reports/m34/phase5/pattern_discovery.json")
    parser.add_argument("--institutional-learning-json", default="reports/m34/phase5/institutional_learning.json")
    parser.add_argument("--analyst-performance-json", default="reports/m34/phase5/analyst_performance.json")
    parser.add_argument("--output-dir", default="reports/m34/phase5/dashboard")
    args = parser.parse_args()

    dashboard = KnowledgeDashboardEngine().build(
        knowledge_base=_load(args.knowledge_base_json),
        pattern_discovery=_load(args.pattern_discovery_json),
        institutional_learning=_load(args.institutional_learning_json),
        analyst_performance=_load(args.analyst_performance_json),
    )

    output_dir = Path(args.output_dir)
    html_path = write_knowledge_dashboard_html(dashboard, output_dir / "knowledge_dashboard.html")
    json_path = write_knowledge_dashboard_json(dashboard, output_dir / "knowledge_dashboard.json")
    summary_path = write_knowledge_dashboard_summary(dashboard, output_dir / "knowledge_dashboard_summary.json")

    print("Milestone 34 Phase 5 Step 5 knowledge dashboard completed.")
    print(f"HTML dashboard: {html_path}")
    print(f"JSON dashboard: {json_path}")
    print(f"Summary: {summary_path}")
    print(f"Governance status: {dashboard.governance_status}")
    print(f"Readiness score: {dashboard.readiness_score:.3f}")
    print(f"Readiness grade: {dashboard.readiness_grade}")


if __name__ == "__main__":
    main()
