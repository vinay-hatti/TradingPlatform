from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from .option_chain_serialization import (
    write_option_chain_inspection_atomic,
)
from .option_chain_service import OptionChainInspectionService


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Option-chain input not found: {path}")

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in (
            "contracts",
            "option_chain",
            "options",
            "records",
            "data",
            "items",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [
                    item for item in value if isinstance(item, dict)
                ]
    raise ValueError(f"Unsupported option-chain payload: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 6 option-chain inspection"
        )
    )
    parser.add_argument("--option-chain-file", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--expiry")
    parser.add_argument("--option-type", choices=("CALL", "PUT"))
    parser.add_argument("--min-volume", type=int, default=0)
    parser.add_argument("--min-open-interest", type=int, default=0)
    parser.add_argument("--max-spread-pct", type=float, default=1.0)
    parser.add_argument(
        "--historical-allow-missing-quotes",
        action="store_true",
        help=(
            "Allow contracts without bid/ask when processing historical "
            "datasets. Contracts are marked HISTORICAL_NO_QUOTE."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/option_chain"
        ),
    )
    parser.add_argument("--show-diagnostics", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = _load_records(args.option_chain_file)
    quote_policy = (
        OptionChainInspectionService.HISTORICAL_ALLOW_MISSING_QUOTES
        if args.historical_allow_missing_quotes
        else OptionChainInspectionService.STRICT
    )
    profile = OptionChainInspectionService().inspect(
        records,
        args.symbol,
        min_volume=args.min_volume,
        min_open_interest=args.min_open_interest,
        max_spread_pct=args.max_spread_pct,
        expiry=args.expiry,
        option_type=args.option_type,
        quote_policy=quote_policy,
    )

    output_path = (
        args.output_dir
        / f"{profile.symbol.lower()}_option_chain_inspection.json"
    )
    write_option_chain_inspection_atomic(output_path, profile)

    payload = {
        "symbol": profile.symbol,
        "input_records": len(records),
        "total_contracts": profile.total_contracts,
        "filtered_contracts": profile.filtered_contracts,
        "expiries": list(profile.expiries),
        "calls": len(profile.calls),
        "puts": len(profile.puts),
        "warnings": list(profile.warnings),
        "quote_policy": profile.quote_policy,
        "output_json": str(output_path),
    }
    if args.show_diagnostics or profile.filtered_contracts == 0:
        payload["rejection_counts"] = profile.rejection_counts
        payload["field_coverage"] = profile.field_coverage
        payload["observed_ranges"] = profile.observed_ranges

    print(json.dumps(payload, indent=2))
    return 0
