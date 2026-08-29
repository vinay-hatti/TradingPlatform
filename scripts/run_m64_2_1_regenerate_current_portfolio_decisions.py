#!/usr/bin/env python
"""Backward-compatible entry point for governed M64.2.4.3 regeneration."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.orchestration import (
    M64CycleBusyError,
    M64HistoryCleanupIncompleteError,
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.portfolio_risk_allocation.history_governance import (
    M64DecisionHistoryPurgeService,
)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main(*, require_governed_purge: bool = False) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate and atomically publish complete current M64 decisions"
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    risk_group = parser.add_mutually_exclusive_group()
    risk_group.add_argument(
        "--risk-snapshot-id",
        help="Pin regeneration to one existing READY governed M64.2 risk snapshot",
    )
    risk_group.add_argument(
        "--rebuild-risk",
        action="store_true",
        help="Build a fresh risk snapshot before regenerating decisions",
    )
    parser.add_argument(
        "--lock-timeout-seconds",
        type=float,
        default=30.0,
        help="Maximum bounded wait for another authoritative M64 cycle",
    )
    parser.add_argument(
        "--confirm-purge-known-invalid-history",
        action="store_true",
        help=(
            "Confirm the M64.2.4.3 protected-row purge of known-invalid, "
            "unreferenced M64 decision history"
        ),
    )
    parser.add_argument(
        "--purge-manifest-output",
        default="m64_2_4_3_purge_manifest.json",
        help="Durable JSON forensic manifest for the governed purge",
    )
    args = parser.parse_args()
    if require_governed_purge and not args.confirm_purge_known_invalid_history:
        parser.error(
            "M64.2.4.3 recovery requires "
            "--confirm-purge-known-invalid-history"
        )
    if args.confirm_purge_known_invalid_history and not args.risk_snapshot_id:
        parser.error(
            "Governed history purge requires --risk-snapshot-id"
        )
    risk_mode = (
        "PINNED" if args.risk_snapshot_id
        else "REBUILT" if args.rebuild_risk
        else "LATEST_READY_REUSE"
    )
    print(
        f"M64.2.4.3 regeneration started for {args.portfolio_id}; "
        f"risk mode={risk_mode}; "
        f"governed purge={args.confirm_purge_known_invalid_history}; "
        "existing published authority remains active until validation completes.",
        file=sys.stderr,
        flush=True,
    )
    last_stage = "operator_start"
    purge_manifest: dict | None = None
    manifest_path = Path(args.purge_manifest_output).expanduser().resolve()
    if args.confirm_purge_known_invalid_history:
        _write_json_atomic(manifest_path, {
            "version": "M64.2.4.3-GOVERNED-PURGE-MANIFEST-1.0",
            "status": "OPERATOR_STARTED",
            "portfolio_id": args.portfolio_id,
            "target_risk_snapshot_id": args.risk_snapshot_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

    def progress(stage: str, details: dict) -> None:
        nonlocal last_stage, purge_manifest
        last_stage = stage
        if stage == "invalid_history_purge_committed":
            purge_manifest = dict(details)
            _write_json_atomic(manifest_path, purge_manifest)
        print(json.dumps({
            "version": "M64.2.4.3-REGENERATION-PROGRESS-1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "portfolio_id": args.portfolio_id,
            "stage": stage,
            "details": details,
        }, sort_keys=True, default=str), file=sys.stderr, flush=True)

    try:
        result = Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(
            args.portfolio_id,
            actor="m64-2-4-3-governed-purge-recovery",
            risk_snapshot_id=args.risk_snapshot_id,
            reuse_latest_ready_risk=not args.rebuild_risk and not args.risk_snapshot_id,
            lock_timeout_seconds=args.lock_timeout_seconds,
            purge_known_invalid_history=
                args.confirm_purge_known_invalid_history,
            purge_confirmation_token=(
                M64DecisionHistoryPurgeService.CONFIRMATION_TOKEN
                if args.confirm_purge_known_invalid_history
                else None
            ),
            progress=progress,
        )
    except M64CycleBusyError as exc:
        print(json.dumps({
            "version": "M64.2.4.3-CURRENT-DECISION-REGENERATION-1.0",
            **exc.as_dict(),
            "risk_snapshot_mode": risk_mode,
            "last_completed_stage": last_stage,
        }, indent=2), file=sys.stderr)
        return 75
    except M64HistoryCleanupIncompleteError as exc:
        print(json.dumps({
            "version": "M64.2.4.3-CURRENT-DECISION-REGENERATION-1.0",
            **exc.as_dict(),
            "risk_snapshot_mode": risk_mode,
            "last_completed_stage": last_stage,
        }, indent=2), file=sys.stderr)
        return 75
    except Exception as exc:
        print(json.dumps({
            "version": "M64.2.4.3-CURRENT-DECISION-REGENERATION-1.0",
            "portfolio_id": args.portfolio_id,
            "status": "FAILED",
            "risk_snapshot_mode": risk_mode,
            "last_completed_stage": last_stage,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, indent=2), file=sys.stderr)
        return 2
    if purge_manifest is not None:
        _write_json_atomic(manifest_path, purge_manifest)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
