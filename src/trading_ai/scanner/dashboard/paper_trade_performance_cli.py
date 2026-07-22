from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from .paper_trade_performance_serialization import (
    write_performance_report_atomic,
)
from .paper_trade_performance_service import (
    PaperTradePerformanceService,
)


def _load_json_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected JSON object: {path}"
        )
    return payload


def _load_marks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Position-mark file not found: {path}"
        )
    if path.suffix.lower() == ".csv":
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]
    if isinstance(payload, dict):
        for key in (
            "marks",
            "positions",
            "records",
            "data",
            "items",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [
                    item
                    for item in value
                    if isinstance(item, dict)
                ]
    raise ValueError(
        f"Unsupported mark payload: {path}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 11 paper-trade "
            "performance tracking and reporting"
        )
    )
    parser.add_argument(
        "--lifecycle-dir",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/paper_trade"
        ),
    )
    parser.add_argument(
        "--mark-file",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/performance/"
            "paper_trade_performance.json"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    lifecycle_files = sorted(
        args.lifecycle_dir.glob("*_lifecycle.json")
    )
    lifecycle_payloads = [
        _load_json_payload(path)
        for path in lifecycle_files
    ]
    marks = _load_marks(args.mark_file)

    report = PaperTradePerformanceService().evaluate(
        lifecycle_payloads,
        marks,
    )
    write_performance_report_atomic(
        args.output_file,
        report,
    )

    summary = report.summary
    print(
        json.dumps(
            {
                "total_positions": (
                    summary.total_positions
                ),
                "open_positions": (
                    summary.open_positions
                ),
                "closed_positions": (
                    summary.closed_positions
                ),
                "winning_positions": (
                    summary.winning_positions
                ),
                "losing_positions": (
                    summary.losing_positions
                ),
                "total_realized_pnl": (
                    summary.total_realized_pnl
                ),
                "total_unrealized_pnl": (
                    summary.total_unrealized_pnl
                ),
                "total_pnl": summary.total_pnl,
                "win_rate": summary.win_rate,
                "average_return_pct": (
                    summary.average_return_pct
                ),
                "warnings": list(report.warnings),
                "output_json": str(args.output_file),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
