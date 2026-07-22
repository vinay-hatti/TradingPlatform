from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .paper_trade_lifecycle_serialization import (
    write_lifecycle_record_atomic,
)
from .paper_trade_lifecycle_service import (
    PaperTradeLifecycleService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 10 paper trade "
            "submission and lifecycle tracking"
        )
    )
    parser.add_argument(
        "--paper-trade-preparation-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--fill-mode",
        choices=("IMMEDIATE", "PENDING"),
        default="IMMEDIATE",
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/paper_trade"
        ),
    )
    parser.add_argument(
        "--registry-file",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/paper_trade/"
            "paper_order_registry.json"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.paper_trade_preparation_json.exists():
        raise FileNotFoundError(
            "Paper-trade preparation artifact not found: "
            f"{args.paper_trade_preparation_json}"
        )

    payload = json.loads(
        args.paper_trade_preparation_json.read_text(
            encoding="utf-8"
        )
    )
    record = PaperTradeLifecycleService().submit(
        payload,
        registry_path=args.registry_file,
        fill_mode=args.fill_mode,
        quantity=args.quantity,
    )

    symbol = record.order.symbol.lower() or "unknown"
    output_path = (
        args.output_dir
        / f"{symbol}_{record.order.order_id.lower()}_lifecycle.json"
    )
    write_lifecycle_record_atomic(
        output_path,
        record,
    )

    print(
        json.dumps(
            {
                "order_id": record.order.order_id,
                "idempotency_key": (
                    record.order.idempotency_key
                ),
                "symbol": record.order.symbol,
                "strategy_id": record.order.strategy_id,
                "order_status": record.order.status,
                "duplicate_submission": (
                    record.duplicate_submission
                ),
                "average_fill_debit": (
                    record.order.average_fill_debit
                ),
                "position_id": (
                    record.position.position_id
                    if record.position
                    else None
                ),
                "position_status": (
                    record.position.status
                    if record.position
                    else None
                ),
                "events": [
                    event.event_type
                    for event in record.events
                ],
                "warnings": list(record.warnings),
                "output_json": str(output_path),
                "registry_file": str(args.registry_file),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
