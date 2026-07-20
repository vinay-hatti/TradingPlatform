from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.decision_journal import (
    DecisionJournalEngine,
    write_decision_journal_report,
)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: _namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_namespace(item) for item in value)
    return value


def demo_journal_input(actor: str) -> dict[str, Any]:
    return {
        "journal_id": "JOURNAL-001",
        "actor": actor,
        "decision_rationale": (
            "The scenario comparison supports continued monitoring "
            "with execution contingent on independent approval."
        ),
        "primary_risks": [
            "Unexpected volatility expansion",
            "Breakdown below primary support",
        ],
        "monitoring_plan": [
            "Review scenario probabilities daily",
            "Monitor implied volatility and liquidity",
        ],
        "reviews": [
            {
                "review_id": "REVIEW-001",
                "reviewer": "Independent Reviewer",
                "reviewed_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "review_status": "APPROVED",
                "reviewer_confidence": 0.80,
                "comments": (
                    "Research evidence and scenario structure are "
                    "sufficient for the recommended action."
                ),
                "required_actions": [],
                "execution_approved": True,
            }
        ],
        "thesis_revisions": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Milestone 34 Phase 4 decision journal."
        )
    )
    parser.add_argument("--research-case-json", required=True)
    parser.add_argument(
        "--scenario-comparison-json",
        required=True,
    )
    parser.add_argument("--journal-input-json")
    parser.add_argument("--actor", default="Research Analyst")
    parser.add_argument(
        "--output",
        default="reports/m34/phase4/decision_journal.json",
    )
    parser.add_argument(
        "--write-template",
        help="Write an editable journal input and exit.",
    )
    args = parser.parse_args()

    if args.write_template:
        path = Path(args.write_template)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                demo_journal_input(args.actor),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Decision-journal input template: {path}")
        return

    case_path = Path(args.research_case_json)
    comparison_path = Path(args.scenario_comparison_json)
    if not case_path.exists():
        raise FileNotFoundError(
            f"Research-case report not found: {case_path}"
        )
    if not comparison_path.exists():
        raise FileNotFoundError(
            "Scenario-comparison report not found: "
            f"{comparison_path}"
        )

    research_case = _namespace(
        json.loads(case_path.read_text(encoding="utf-8"))
    )
    scenario_comparison = _namespace(
        json.loads(
            comparison_path.read_text(encoding="utf-8")
        )
    )

    if args.journal_input_json:
        input_path = Path(args.journal_input_json)
        if not input_path.exists():
            raise FileNotFoundError(
                f"Journal input not found: {input_path}"
            )
        journal_input = json.loads(
            input_path.read_text(encoding="utf-8")
        )
    else:
        journal_input = demo_journal_input(args.actor)

    result = DecisionJournalEngine().build(
        journal_id=str(
            journal_input.get("journal_id", "JOURNAL-001")
        ),
        research_case=research_case,
        scenario_comparison=scenario_comparison,
        actor=str(journal_input.get("actor", args.actor)),
        decision_rationale=str(
            journal_input.get("decision_rationale", "")
        ),
        primary_risks=tuple(
            journal_input.get("primary_risks", ())
        ),
        monitoring_plan=tuple(
            journal_input.get("monitoring_plan", ())
        ),
        reviews=tuple(journal_input.get("reviews", ())),
        thesis_revisions=tuple(
            journal_input.get("thesis_revisions", ())
        ),
    )
    output = write_decision_journal_report(
        result, args.output
    )

    print("Milestone 34 Phase 4 decision journal completed.")
    print(f"Output: {output}")
    print(f"Decision action: {result.decision_action}")
    print(f"Decision status: {result.decision_status}")
    print(f"Approval status: {result.approval_status}")
    print(f"Execution allowed: {result.execution_allowed}")


if __name__ == "__main__":
    main()
