from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .strategy_comparison_serialization import (
    write_strategy_comparison_atomic,
)
from .strategy_comparison_service import StrategyComparisonService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 7 strategy comparison"
        )
    )
    parser.add_argument(
        "--option-chain-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--direction",
        choices=("CALL", "PUT"),
        required=True,
    )
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--min-volume", type=int, default=0)
    parser.add_argument("--min-open-interest", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/strategy_comparison"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.option_chain_json.exists():
        raise FileNotFoundError(
            f"Option-chain artifact not found: {args.option_chain_json}"
        )

    payload = json.loads(
        args.option_chain_json.read_text(encoding="utf-8")
    )
    profile = StrategyComparisonService().compare(
        payload,
        direction=args.direction,
        max_candidates=args.max_candidates,
        min_open_interest=args.min_open_interest,
        min_volume=args.min_volume,
    )

    output_path = (
        args.output_dir
        / (
            f"{profile.symbol.lower()}_"
            f"{profile.direction.lower()}_strategy_comparison.json"
        )
    )
    write_strategy_comparison_atomic(output_path, profile)

    top = (
        profile.ranked_strategies[0].to_dict()
        if profile.ranked_strategies
        else None
    )
    print(
        json.dumps(
            {
                "symbol": profile.symbol,
                "direction": profile.direction,
                "source_contracts": profile.source_contracts,
                "generated_strategies": profile.generated_strategies,
                "ranked_strategies": len(profile.ranked_strategies),
                "top_strategy": top,
                "warnings": list(profile.warnings),
                "output_json": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
