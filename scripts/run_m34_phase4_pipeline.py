from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.research_workstation.phase4_pipeline import (
    Phase4PipelineEngine,
)

from run_m34_phase4_research_case import demo_research_case


def demo_manifest(
    *,
    case_id: str,
    symbol: str,
    strategy_name: str,
):
    return {
        "research_case": demo_research_case(
            case_id=case_id,
            symbol=symbol,
            strategy_name=strategy_name,
        ),
        "sensitivity_inputs": {
            "implied_volatility": {
                "baseline": 0.24,
                "stressed": 0.25,
                "notes": (
                    "Evaluate a controlled volatility expansion."
                ),
            },
            "underlying_price": {
                "baseline": 200.0,
                "stressed": 210.0,
                "notes": (
                    "Evaluate an upside price scenario."
                ),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Milestone 34 Phase 4 Steps 1 and 2 end to end."
        )
    )
    parser.add_argument("--input-json")
    parser.add_argument("--case-id", default="CASE-001")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--strategy-name",
        "--strategy",
        dest="strategy_name",
        default="BULL_PUT_SPREAD",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m34/phase4",
    )
    parser.add_argument(
        "--write-template",
        help="Write an editable Phase 4 pipeline manifest and exit.",
    )
    args = parser.parse_args()

    if args.write_template:
        path = Path(args.write_template)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = demo_manifest(
            case_id=args.case_id,
            symbol=args.symbol.upper(),
            strategy_name=args.strategy_name.upper(),
        )
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Phase 4 pipeline input template: {path}")
        return

    if args.input_json:
        input_path = Path(args.input_json)
        if not input_path.exists():
            raise FileNotFoundError(
                f"Phase 4 input manifest not found: {input_path}"
            )
        manifest = json.loads(
            input_path.read_text(encoding="utf-8")
        )
        mode = f"manifest: {input_path}"
    else:
        manifest = demo_manifest(
            case_id=args.case_id,
            symbol=args.symbol.upper(),
            strategy_name=args.strategy_name.upper(),
        )
        mode = "deterministic demo manifest"

    result = Phase4PipelineEngine().run(
        manifest=manifest,
        output_directory=args.output_dir,
    )

    print("Milestone 34 Phase 4 Steps 1-2 completed.")
    print(f"Input mode: {mode}")
    print(f"Research case: {result.research_case_report}")
    print(
        "Scenario comparison: "
        f"{result.scenario_comparison_report}"
    )
    print(f"Pipeline report: {result.pipeline_report}")
    print(
        f"Research case status: {result.research_case_status}"
    )
    print(
        "Scenario comparison status: "
        f"{result.scenario_comparison_status}"
    )
    print(
        f"Recommendation: {result.recommendation_action}"
    )


if __name__ == "__main__":
    main()
