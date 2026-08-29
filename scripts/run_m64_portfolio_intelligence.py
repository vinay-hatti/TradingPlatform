#!/usr/bin/env python
"""Dedicated scheduled owner of the M64 authoritative portfolio cycle."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
import time

from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.orchestration import (
    M64CycleBusyError,
    Milestone64ContinuousPortfolioIntelligenceService,
)


def emit_progress(portfolio_id: str):
    def progress(stage: str, details: dict) -> None:
        print(json.dumps({
            "version": "M64.2.4.7-SCHEDULED-PROGRESS-1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "portfolio_id": portfolio_id,
            "stage": stage,
            "details": details,
        }, sort_keys=True, default=str), file=sys.stderr, flush=True)
    return progress


def run(
    portfolio_id: str = "PAPER-PRIMARY",
    *,
    lock_timeout_seconds: float = 0.0,
    force_authoritative_rebuild: bool = False,
):
    progress = emit_progress(portfolio_id)
    try:
        return Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(
            portfolio_id,
            actor="m64-dedicated-scheduled-owner",
            skip_unchanged_authority=not force_authoritative_rebuild,
            lock_timeout_seconds=lock_timeout_seconds,
            progress=progress,
        )
    except M64CycleBusyError as exc:
        # A scheduled overlap defers cleanly. Historical retention is bounded,
        # asynchronous, and never blocks an authoritative publication.
        result = exc.as_dict()
        progress("cycle_deferred_busy", result)
        return {
            "version": "M64.2.4.7-SCHEDULED-CYCLE-1.0",
            **result,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run cumulative Milestone 64 portfolio intelligence"
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument(
        "--lock-timeout-seconds",
        type=float,
        default=0.0,
        help="Scheduled runs defer immediately when another M64 cycle is active",
    )
    parser.add_argument(
        "--force-authoritative-rebuild",
        action="store_true",
        help="Bypass unchanged-input no-op detection for this invocation",
    )
    args = parser.parse_args()
    while True:
        result = run(
            args.portfolio_id,
            lock_timeout_seconds=args.lock_timeout_seconds,
            force_authoritative_rebuild=args.force_authoritative_rebuild,
        )
        print(json.dumps(result, indent=2, sort_keys=True, default=str), flush=True)
        if not args.daemon:
            return 0
        time.sleep(max(60, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
