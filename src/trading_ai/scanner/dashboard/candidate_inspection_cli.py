from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .candidate_inspection_serialization import (
    write_candidate_inspection_atomic,
)
from .candidate_inspection_service import CandidateInspectionService
from .filter_cli import _load_filter_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 5 candidate inspection and handoff"
        )
    )
    parser.add_argument("--rankings-json", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/candidate_inspection"
        ),
    )
    parser.add_argument("--print-handoff-commands", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    resolved_path, records = _load_filter_records(args.rankings_json)

    try:
        profile = CandidateInspectionService().inspect(
            records,
            args.symbol,
        )
    except (KeyError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "reason": str(exc),
                    "rankings_input": str(resolved_path),
                },
                indent=2,
            )
        )
        return 2

    output_path = (
        args.output_dir
        / f"{profile.symbol.lower()}_candidate_inspection.json"
    )
    write_candidate_inspection_atomic(output_path, profile)

    payload = {
        "status": "READY",
        "rankings_input": str(resolved_path),
        "symbol": profile.symbol,
        "institutional_score": profile.institutional_score,
        "probability_of_profit": profile.probability_of_profit,
        "direction": profile.direction,
        "strategy_type": profile.strategy_type,
        "output_json": str(output_path),
    }
    if args.print_handoff_commands:
        payload["option_chain_command"] = list(
            profile.option_chain_command
        )
        payload["strategy_comparison_command"] = list(
            profile.strategy_comparison_command
        )
        payload["institutional_decision_command"] = list(
            profile.institutional_decision_command
        )

    print(json.dumps(payload, indent=2))
    return 0
