#!/usr/bin/env python
"""Resumably requalify the current Institutional Options publication.

This operator command intentionally keeps historical strategy and contract
rows.  It repairs only the lifecycle of the latest materialized Stock
Intelligence run, in committed batches, while holding the same portfolio-cycle
advisory lock used by M64.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from trading_ai.database.engine import engine
from trading_ai.institutional_options.decision import InstitutionalDecisionService
from trading_ai.institutional_options.domain import OpportunityState
from trading_ai.institutional_options.models import InstitutionalOpportunityModel
from trading_ai.institutional_options.publication_scope import (
    latest_stock_scanner_run_id,
)

BUSY_EXIT = 75
INCOMPLETE_EXIT = 3


def _event(name: str, **payload: object) -> None:
    print(
        json.dumps(
            {
                "event": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **payload,
            },
            sort_keys=True,
            default=str,
        ),
        file=sys.stderr,
        flush=True,
    )


def _state_counts(session: Session, stock_scanner_run_id: str) -> dict[str, int]:
    rows = (
        session.query(
            InstitutionalOpportunityModel.state,
            func.count(InstitutionalOpportunityModel.opportunity_id),
        )
        .filter(
            InstitutionalOpportunityModel.stock_scanner_run_id
            == stock_scanner_run_id
        )
        .group_by(InstitutionalOpportunityModel.state)
        .order_by(InstitutionalOpportunityModel.state)
        .all()
    )
    return {str(state): int(count) for state, count in rows}


def _next_batch(
    session: Session,
    *,
    stock_scanner_run_id: str,
    batch_size: int,
    attempted: set[str],
) -> tuple[str, ...]:
    query = (
        session.query(InstitutionalOpportunityModel.opportunity_id)
        .filter(
            InstitutionalOpportunityModel.stock_scanner_run_id
            == stock_scanner_run_id,
            InstitutionalOpportunityModel.state
            == OpportunityState.CONTRACTS_OPTIMIZED.value,
        )
        .order_by(
            desc(InstitutionalOpportunityModel.overall_score),
            InstitutionalOpportunityModel.symbol,
            InstitutionalOpportunityModel.opportunity_id,
        )
    )
    if attempted:
        query = query.filter(
            ~InstitutionalOpportunityModel.opportunity_id.in_(tuple(attempted))
        )
    return tuple(str(value) for (value,) in query.limit(batch_size).all())


def recover(
    *,
    portfolio_id: str,
    batch_size: int,
    max_batches: int | None,
    dry_run: bool,
) -> tuple[dict[str, object], int]:
    lock_key = f"trading_ai:m64_authoritative_cycle:{portfolio_id}"
    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:lock_key))"),
                {"lock_key": lock_key},
            ).scalar_one()
        )
        connection.commit()
        if not acquired:
            result = {
                "status": "BUSY",
                "portfolio_id": portfolio_id,
                "lock_key": lock_key,
                "message": "M64 authoritative portfolio cycle is already running",
            }
            _event("requalification_busy", **result)
            return result, BUSY_EXIT

        try:
            with Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
            ) as session:
                stock_scanner_run_id = latest_stock_scanner_run_id(session)
                if stock_scanner_run_id is None:
                    result = {
                        "status": "NO_CURRENT_MATERIALIZED_STOCK_RUN",
                        "portfolio_id": portfolio_id,
                    }
                    return result, INCOMPLETE_EXIT

                before = _state_counts(session, stock_scanner_run_id)
                result: dict[str, object] = {
                    "version": "M77.0.3-INSTITUTIONAL-OPTIONS-REQUALIFICATION-1.0",
                    "portfolio_id": portfolio_id,
                    "stock_scanner_run_id": stock_scanner_run_id,
                    "dry_run": dry_run,
                    "batch_size": batch_size,
                    "max_batches": max_batches,
                    "before_state_counts": before,
                }
                _event(
                    "requalification_started",
                    portfolio_id=portfolio_id,
                    stock_scanner_run_id=stock_scanner_run_id,
                    before_state_counts=before,
                    dry_run=dry_run,
                )
                if dry_run:
                    result.update(
                        {
                            "status": "DRY_RUN",
                            "remaining_contracts_optimized": before.get(
                                OpportunityState.CONTRACTS_OPTIMIZED.value,
                                0,
                            ),
                        }
                    )
                    return result, 0

                attempted: set[str] = set()
                totals: Counter[str] = Counter()
                errors: list[str] = []
                batches = 0
                while max_batches is None or batches < max_batches:
                    opportunity_ids = _next_batch(
                        session,
                        stock_scanner_run_id=stock_scanner_run_id,
                        batch_size=batch_size,
                        attempted=attempted,
                    )
                    if not opportunity_ids:
                        break
                    attempted.update(opportunity_ids)
                    batches += 1
                    try:
                        batch_result = InstitutionalDecisionService(session).build(
                            opportunity_ids=opportunity_ids,
                            limit=None,
                        )
                        session.commit()
                        for key in (
                            "requested",
                            "created",
                            "refreshed",
                            "failed",
                            "prerequisite_requested",
                            "valuation_failed",
                            "management_failed",
                            "remaining_contracts_optimized",
                        ):
                            totals[key] += int(getattr(batch_result, key))
                        errors.extend(batch_result.errors)
                        _event(
                            "requalification_batch_committed",
                            batch=batches,
                            batch_size=len(opportunity_ids),
                            requested=batch_result.requested,
                            created=batch_result.created,
                            refreshed=batch_result.refreshed,
                            failed=batch_result.failed,
                            valuation_failed=batch_result.valuation_failed,
                            management_failed=batch_result.management_failed,
                            remaining_contracts_optimized=(
                                batch_result.remaining_contracts_optimized
                            ),
                        )
                    except Exception as exc:
                        session.rollback()
                        totals["failed"] += len(opportunity_ids)
                        detail = f"batch {batches}: {type(exc).__name__}: {exc}"
                        errors.append(detail)
                        _event(
                            "requalification_batch_rolled_back",
                            batch=batches,
                            batch_size=len(opportunity_ids),
                            error=detail,
                        )

                after = _state_counts(session, stock_scanner_run_id)
                remaining = after.get(OpportunityState.CONTRACTS_OPTIMIZED.value, 0)
                status = "READY" if remaining == 0 and not errors else "INCOMPLETE"
                result.update(
                    {
                        "status": status,
                        "batches_committed_or_attempted": batches,
                        "attempted_opportunities": len(attempted),
                        "totals": dict(totals),
                        "errors": errors,
                        "after_state_counts": after,
                        "remaining_contracts_optimized": remaining,
                        "historical_rows_deleted": 0,
                    }
                )
                _event(
                    "requalification_finished",
                    status=status,
                    batches=batches,
                    attempted=len(attempted),
                    remaining_contracts_optimized=remaining,
                    error_count=len(errors),
                    after_state_counts=after,
                )
                return result, 0 if status == "READY" else INCOMPLETE_EXIT
        finally:
            connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:lock_key))"),
                {"lock_key": lock_key},
            )
            connection.commit()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resumably requalify CONTRACTS_OPTIMIZED opportunities from the "
            "latest materialized Stock Intelligence run"
        )
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Stop after this many committed/attempted batches; rerun to resume",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.batch_size <= 200:
        raise SystemExit("--batch-size must be between 1 and 200")
    if args.max_batches is not None and args.max_batches < 1:
        raise SystemExit("--max-batches must be at least 1")
    result, exit_code = recover(
        portfolio_id=args.portfolio_id,
        batch_size=args.batch_size,
        max_batches=args.max_batches,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
