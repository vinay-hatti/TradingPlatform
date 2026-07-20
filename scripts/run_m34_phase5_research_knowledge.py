from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.research_knowledge import (
    ResearchKnowledgeEngine,
    write_research_index,
    write_research_knowledge_base,
)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: _namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_namespace(item) for item in value)
    return value


def _load(path: Path, *, required: bool = True) -> Any | None:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        return None
    return _namespace(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Milestone 34 Phase 5 Step 1 research knowledge base."
        )
    )
    parser.add_argument(
        "--phase4-dir",
        default="reports/m34/phase4",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m34/phase5",
    )
    parser.add_argument(
        "--knowledge-base-id",
        default="M34-PHASE5-KB-001",
    )
    parser.add_argument(
        "--additional-tags-json",
        default=None,
    )
    args = parser.parse_args()

    phase4_dir = Path(args.phase4_dir)
    output_dir = Path(args.output_dir)

    research_case = _load(phase4_dir / "research_case.json")
    scenario_comparison = _load(
        phase4_dir / "scenario_comparison.json"
    )
    decision_journal = _load(
        phase4_dir / "decision_journal.json"
    )
    outcome_attribution = _load(
        phase4_dir / "outcome_attribution.json",
        required=False,
    )
    thesis_report = _load(
        phase4_dir / "thesis_validation.json",
        required=False,
    )
    dashboard_summary = _load(
        phase4_dir
        / "dashboard"
        / "research_dashboard_summary.json",
        required=False,
    )

    thesis_validation = None
    if thesis_report is not None:
        thesis_validation = getattr(
            thesis_report,
            "thesis_validation",
            thesis_report,
        )

    additional_tags = []
    if args.additional_tags_json:
        path = Path(args.additional_tags_json)
        additional_tags = json.loads(
            path.read_text(encoding="utf-8")
        )

    engine = ResearchKnowledgeEngine()
    knowledge_case = engine.build_case(
        research_case=research_case,
        scenario_comparison=scenario_comparison,
        decision_journal=decision_journal,
        outcome_attribution=outcome_attribution,
        thesis_validation=thesis_validation,
        dashboard_summary=dashboard_summary,
        additional_tags=additional_tags,
    )
    knowledge_base = engine.build_knowledge_base(
        knowledge_base_id=args.knowledge_base_id,
        cases=(knowledge_case,),
    )

    knowledge_path = write_research_knowledge_base(
        knowledge_base,
        output_dir / "research_knowledge_base.json",
    )
    index_path = write_research_index(
        knowledge_base,
        output_dir / "research_index.json",
    )

    print(
        "Milestone 34 Phase 5 Step 1 research knowledge base completed."
    )
    print(f"Knowledge base: {knowledge_path}")
    print(f"Research index: {index_path}")
    print(f"Governance status: {knowledge_base.governance_status}")
    print(f"Cases indexed: {knowledge_base.case_count}")
    print(f"Records indexed: {knowledge_base.record_count}")
    print(f"Tags indexed: {knowledge_base.tag_count}")


if __name__ == "__main__":
    main()
