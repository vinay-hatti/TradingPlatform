from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.analyst_performance import (
    AnalystPerformanceEngine,
    write_analyst_performance,
    write_analyst_scorecards,
)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: _namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_namespace(item) for item in value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Milestone 34 Phase 5 Step 4 analyst performance analytics."
        )
    )
    parser.add_argument(
        "--knowledge-base-json",
        default="reports/m34/phase5/research_knowledge_base.json",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m34/phase5",
    )
    args = parser.parse_args()

    source = Path(args.knowledge_base_json)
    if not source.exists():
        raise FileNotFoundError(f"Knowledge base not found: {source}")

    knowledge_base = _namespace(
        json.loads(source.read_text(encoding="utf-8"))
    )
    output_dir = Path(args.output_dir)

    report = AnalystPerformanceEngine().build_report(
        knowledge_base=knowledge_base
    )

    performance_path = write_analyst_performance(
        report,
        output_dir / "analyst_performance.json",
    )
    scorecards_path = write_analyst_scorecards(
        report,
        output_dir / "analyst_scorecards.json",
    )

    print(
        "Milestone 34 Phase 5 Step 4 analyst performance completed."
    )
    print(f"Performance report: {performance_path}")
    print(f"Scorecards report: {scorecards_path}")
    print(f"Governance status: {report.governance_status}")
    print(f"Analysts: {report.analyst_count}")
    print(f"Cases: {report.total_case_count}")

    for scorecard in report.scorecards:
        print(
            f"{scorecard.analyst_id}: "
            f"{scorecard.composite_score:.3f} "
            f"({scorecard.rating})"
        )


if __name__ == "__main__":
    main()
