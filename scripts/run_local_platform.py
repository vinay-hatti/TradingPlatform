from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]

WORKFLOWS: dict[str, tuple[str, ...]] = {
    "research": (
        "scripts/run_market_ingestion.py",
        "scripts/run_indicators.py",
        "scripts/run_daily_scan.py",
        "scripts/build_dashboard.py",
    ),
    "paper": (
        "scripts/run_market_ingestion.py",
        "scripts/run_daily_scan.py",
        "scripts/mark_paper_positions.py",
        "scripts/paper_trade_from_optimizer.py",
        "scripts/build_dashboard.py",
    ),
    "daily": (
        "scripts/run_paper_daily.py",
    ),
    "full": (
        "scripts/run_market_ingestion.py",
        "scripts/run_indicators.py",
        "scripts/run_full_system.py",
        "scripts/build_dashboard.py",
    ),
}


def execute(
    scripts: Sequence[str],
    *,
    continue_on_error: bool,
    dry_run: bool,
) -> int:
    for relative in scripts:
        path = ROOT / relative
        if not path.is_file():
            print(f"ERROR: workflow script is missing: {path}", file=sys.stderr)
            if continue_on_error:
                continue
            return 2

        command = [sys.executable, str(path)]
        print(f"\n>>> {' '.join(command)}")
        if dry_run:
            continue

        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode != 0:
            print(
                f"FAILED ({completed.returncode}): {relative}",
                file=sys.stderr,
            )
            if not continue_on_error:
                return int(completed.returncode)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an existing TradingPlatform local workflow."
    )
    parser.add_argument(
        "--mode",
        choices=tuple(WORKFLOWS),
        default="paper",
        help="Workflow to run once.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with later stages after a stage failure.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them.",
    )
    args = parser.parse_args()
    return execute(
        WORKFLOWS[args.mode],
        continue_on_error=args.continue_on_error,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
