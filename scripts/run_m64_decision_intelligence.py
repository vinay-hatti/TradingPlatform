#!/usr/bin/env python
"""Run a complete M64.2.4 decision-intelligence cycle."""
from __future__ import annotations

import argparse
import json
import sys

from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.orchestration import (
    M64CycleBusyError,
    M64HistoryCleanupIncompleteError,
    Milestone64ContinuousPortfolioIntelligenceService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a fresh-risk M64.2.4 authoritative portfolio cycle"
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--lock-timeout-seconds",
        type=float,
        default=30.0,
        help="Maximum bounded wait for another authoritative M64 cycle",
    )
    args = parser.parse_args()
    if args.limit is not None:
        parser.error(
            "--limit cannot produce authoritative M64.2.4 coverage; "
            "run the complete current generation"
        )

    def progress(stage: str, details: dict) -> None:
        print(json.dumps({
            "version": "M64.2.4.3-DECISION-PROGRESS-1.0",
            "portfolio_id": args.portfolio_id,
            "stage": stage,
            "details": details,
        }, sort_keys=True, default=str), file=sys.stderr, flush=True)

    try:
        result = Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(
            args.portfolio_id,
            actor="run-m64-decision-intelligence",
            lock_timeout_seconds=args.lock_timeout_seconds,
            progress=progress,
        )
    except (M64CycleBusyError, M64HistoryCleanupIncompleteError) as exc:
        print(json.dumps({
            "version": "M64.2.4.3-DECISION-CYCLE-1.0",
            **exc.as_dict(),
        }, indent=2, default=str), file=sys.stderr)
        return 75
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
