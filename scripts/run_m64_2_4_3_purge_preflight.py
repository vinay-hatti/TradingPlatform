#!/usr/bin/env python
"""Read-only M64.2.4.3 governed purge preflight."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from run_m64_2_1_regenerate_current_portfolio_decisions import (
    _write_json_atomic,
)
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.history_governance import (
    M64DecisionHistoryPurgeService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview protected and purge-eligible M64 decision history"
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--risk-snapshot-id", required=True)
    parser.add_argument(
        "--output",
        default="m64_2_4_3_purge_preflight.json",
    )
    args = parser.parse_args()

    def progress(stage: str, details: dict) -> None:
        print(json.dumps({
            "version": "M64.2.4.3-PURGE-PREFLIGHT-PROGRESS-1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "portfolio_id": args.portfolio_id,
            "stage": stage,
            "details": details,
        }, sort_keys=True, default=str), file=sys.stderr, flush=True)

    try:
        result = M64DecisionHistoryPurgeService(SessionLocal).purge_known_invalid_history(
            args.portfolio_id,
            target_risk_snapshot_id=args.risk_snapshot_id,
            confirmation_token=M64DecisionHistoryPurgeService.CONFIRMATION_TOKEN,
            dry_run=True,
            progress=progress,
        )
        output = Path(args.output).expanduser().resolve()
        _write_json_atomic(output, result)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result.get("status") == "DRY_RUN_COMPLETE" else 2
    except Exception as exc:
        print(json.dumps({
            "version": "M64.2.4.3-PURGE-PREFLIGHT-1.0",
            "status": "FAILED",
            "portfolio_id": args.portfolio_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
