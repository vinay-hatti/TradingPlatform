from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from .paper_trade_preparation_profile import (
    PaperTradePreparationPolicy,
)
from .paper_trade_preparation_serialization import (
    write_paper_trade_preparation_atomic,
)
from .paper_trade_preparation_service import (
    PaperTradePreparationService,
)


def _load_quote_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Quote file not found: {path}"
        )

    if path.suffix.lower() == ".csv":
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [
            item for item in payload
            if isinstance(item, dict)
        ]
    if isinstance(payload, dict):
        for key in (
            "contracts",
            "quotes",
            "option_chain",
            "options",
            "records",
            "data",
            "items",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [
                    item for item in value
                    if isinstance(item, dict)
                ]
    raise ValueError(
        f"Unsupported quote payload: {path}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 9 quote refresh "
            "and paper trade preparation"
        )
    )
    parser.add_argument(
        "--institutional-decision-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--quote-file",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--max-spread-pct",
        type=float,
        default=0.20,
    )
    parser.add_argument(
        "--max-debit-drift-pct",
        type=float,
        default=0.25,
    )
    parser.add_argument(
        "--min-reward-risk-ratio",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--allow-incomplete-quotes",
        action="store_true",
    )
    parser.add_argument(
        "--allow-nonpositive-debit",
        action="store_true",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/paper_trade_preparation"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.institutional_decision_json.exists():
        raise FileNotFoundError(
            "Institutional decision artifact not found: "
            f"{args.institutional_decision_json}"
        )

    decision_payload = json.loads(
        args.institutional_decision_json.read_text(
            encoding="utf-8"
        )
    )
    quote_records = _load_quote_records(args.quote_file)

    policy = PaperTradePreparationPolicy(
        max_spread_pct=args.max_spread_pct,
        max_debit_drift_pct=(
            args.max_debit_drift_pct
        ),
        min_reward_risk_ratio=(
            args.min_reward_risk_ratio
        ),
        require_complete_quotes=(
            not args.allow_incomplete_quotes
        ),
        require_positive_debit=(
            not args.allow_nonpositive_debit
        ),
    )

    record = PaperTradePreparationService().prepare(
        decision_payload,
        quote_records,
        policy=policy,
    )

    output_path = (
        args.output_dir
        / (
            f"{record.symbol.lower()}_"
            f"{record.direction.lower()}_"
            "paper_trade_preparation.json"
        )
    )
    write_paper_trade_preparation_atomic(
        output_path,
        record,
    )

    print(
        json.dumps(
            {
                "symbol": record.symbol,
                "direction": record.direction,
                "strategy_id": record.strategy_id,
                "decision": record.decision,
                "paper_trade_ready": (
                    record.paper_trade_ready
                ),
                "original_debit": (
                    record.original_debit
                ),
                "refreshed_debit": (
                    record.refreshed_debit
                ),
                "debit_drift_pct": (
                    record.debit_drift_pct
                ),
                "reward_risk_ratio": (
                    record.reward_risk_ratio
                ),
                "rejection_reasons": list(
                    record.rejection_reasons
                ),
                "warnings": list(record.warnings),
                "output_json": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
