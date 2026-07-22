from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def _run(command: list[str]) -> None:
    print("$ " + " ".join(command))
    completed = subprocess.run(
        command,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _newest_lifecycle(
    lifecycle_dir: Path,
) -> Path:
    paths = sorted(
        lifecycle_dir.glob("*_lifecycle.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        raise FileNotFoundError(
            f"No lifecycle artifact found in {lifecycle_dir}"
        )
    return paths[0]


def _position_id(lifecycle_path: Path) -> str:
    payload = json.loads(
        lifecycle_path.read_text(encoding="utf-8")
    )
    position = payload.get("position")
    if not isinstance(position, dict):
        raise ValueError(
            "Lifecycle artifact does not contain an open position: "
            f"{lifecycle_path}"
        )
    position_id = str(position.get("position_id", "")).strip()
    if not position_id:
        raise ValueError(
            f"position_id missing from {lifecycle_path}"
        )
    return position_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Milestone 35 Phase 5 Steps 10 through 12 "
            "using real generated artifacts."
        )
    )
    parser.add_argument(
        "--preparation-json",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/"
            "paper_trade_preparation/"
            "amzn_call_paper_trade_preparation.json"
        ),
    )
    parser.add_argument(
        "--current-debit",
        type=float,
        default=1.50,
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    python = sys.executable

    _run(
        [
            python,
            "scripts/test_m35_phase5_step10_paper_trade_lifecycle.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step10_pending_order.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step10_integration.py",
        ]
    )

    _run(
        [
            python,
            "scripts/run_m35_phase5_paper_trade_lifecycle.py",
            "--paper-trade-preparation-json",
            str(args.preparation_json),
            "--fill-mode",
            "IMMEDIATE",
            "--quantity",
            str(args.quantity),
        ]
    )

    lifecycle_dir = Path(
        "reports/m35/phase5/dashboard/paper_trade"
    )
    lifecycle_path = _newest_lifecycle(lifecycle_dir)
    position_id = _position_id(lifecycle_path)

    mark_file = Path(
        "data/options/paper_position_marks.csv"
    )
    mark_file.parent.mkdir(parents=True, exist_ok=True)
    mark_file.write_text(
        "\n".join(
            [
                (
                    "position_id,status,current_debit,"
                    "exit_debit,marked_at,closed_at"
                ),
                (
                    f"{position_id},OPEN,{args.current_debit},,,"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _run(
        [
            python,
            "scripts/test_m35_phase5_step11_performance.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step11_closed_position.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step11_integration.py",
        ]
    )

    _run(
        [
            python,
            "scripts/run_m35_phase5_paper_trade_performance.py",
            "--lifecycle-dir",
            str(lifecycle_dir),
            "--mark-file",
            str(mark_file),
        ]
    )

    _run(
        [
            python,
            "scripts/test_m35_phase5_step12_dashboard_workflow.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step12_incomplete_workflow.py",
        ]
    )
    _run(
        [
            python,
            "scripts/test_m35_phase5_step12_integration.py",
        ]
    )

    _run(
        [
            python,
            "scripts/run_m35_phase5_dashboard_workflow_autodiscovery.py",
        ]
    )

    print(
        json.dumps(
            {
                "status": "VALIDATION_COMPLETED",
                "lifecycle_artifact": str(lifecycle_path),
                "position_id": position_id,
                "mark_file": str(mark_file),
                "next_action": (
                    "Review dashboard_workflow_report.json. "
                    "Any missing earlier-stage artifacts will be "
                    "listed explicitly."
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
