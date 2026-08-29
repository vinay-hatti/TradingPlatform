from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.scenario_comparison import (
    ScenarioComparisonEngine,
    write_scenario_comparison_report,
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
            "Run Milestone 34 Phase 4 scenario comparison and "
            "sensitivity analytics."
        )
    )
    parser.add_argument("--research-case-json", required=True)
    parser.add_argument("--sensitivity-json")
    parser.add_argument(
        "--output",
        default=(
            "reports/m34/phase4/scenario_comparison.json"
        ),
    )
    args = parser.parse_args()

    case_path = Path(args.research_case_json)
    if not case_path.exists():
        raise FileNotFoundError(
            f"Research-case report not found: {case_path}"
        )
    research_case = _namespace(
        json.loads(case_path.read_text(encoding="utf-8"))
    )

    sensitivity_inputs = {}
    if args.sensitivity_json:
        sensitivity_path = Path(args.sensitivity_json)
        if not sensitivity_path.exists():
            raise FileNotFoundError(
                f"Sensitivity input not found: {sensitivity_path}"
            )
        sensitivity_inputs = json.loads(
            sensitivity_path.read_text(encoding="utf-8")
        )

    result = ScenarioComparisonEngine().compare(
        research_case=research_case,
        sensitivity_inputs=sensitivity_inputs,
    )
    output = write_scenario_comparison_report(
        result, args.output
    )

    print("Milestone 34 Phase 4 scenario comparison completed.")
    print(f"Output: {output}")
    print(f"Status: {result.status}")
    print(f"Score: {result.comparison_score:.2f}")
    print(f"Grade: {result.comparison_grade}")
    print(
        f"Recommendation: {result.recommendation.action}"
    )
    print(
        "Weighted expected return: "
        f"{result.weighted_expected_return_pct:.4f}"
    )


if __name__ == "__main__":
    main()
