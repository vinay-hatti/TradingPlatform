from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select, text

from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.models import (
    InflectionPublicationModel,
    InflectionSnapshotModel,
    InflectionTimelineEventModel,
)
from trading_ai.institutional_options.models import InstitutionalOpportunityModel
from trading_ai.institutional_options.publication_scope import (
    latest_stock_intelligence_publication,
)
from trading_ai.stock_intelligence.models import StockScannerPublicationModel


CONFIRMATION = "PURGE_M68_UNMATERIALIZED_AND_DUPLICATE_TIMELINE"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def inspect(session) -> dict:
    target = latest_stock_intelligence_publication(
        session,
        "current_stock_intelligence",
        require_materialized=True,
    )
    if target is None:
        raise LookupError("No materialized Stock Intelligence authority exists")
    target_run = str(target.scanner_run_id)
    inflection = session.execute(
        select(InflectionPublicationModel).where(
            InflectionPublicationModel.publication_name
            == "current_institutional_inflection"
        )
    ).scalars().first()
    rows = session.execute(text("""
        WITH source_runs AS (
            SELECT DISTINCT source_run_id
              FROM institutional_inflection_snapshots
             WHERE source_run_id <> :target_run
        ), unmaterialized AS (
            SELECT s.source_run_id
              FROM source_runs s
             WHERE NOT EXISTS (
                    SELECT 1
                      FROM institutional_option_opportunities o
                     WHERE o.stock_scanner_run_id = s.source_run_id
             )
        )
        SELECT
            (SELECT COUNT(*) FROM unmaterialized) AS rogue_run_count,
            (SELECT COUNT(*)
               FROM institutional_inflection_snapshots i
              WHERE i.source_run_id IN (SELECT source_run_id FROM unmaterialized)
            ) AS rogue_snapshot_count,
            (SELECT COUNT(*)
               FROM institutional_inflection_timeline_events t
              WHERE t.source_run_id IN (SELECT source_run_id FROM unmaterialized)
            ) AS rogue_timeline_count,
            (SELECT COUNT(*)
               FROM stock_scanner_publications p
              WHERE p.scanner_run_id IN (SELECT source_run_id FROM unmaterialized)
            ) AS rogue_stock_publication_count
    """), {"target_run": target_run}).mappings().one()
    duplicate_timeline = session.execute(text("""
        WITH ordered AS (
            SELECT event_id,
                   COALESCE(payload_json::jsonb ->> 'direction', 'UNKNOWN')
                       || '|' || transition_state AS signature,
                   LAG(
                       COALESCE(payload_json::jsonb ->> 'direction', 'UNKNOWN')
                       || '|' || transition_state
                   ) OVER (
                       PARTITION BY symbol, timeframe
                       ORDER BY event_timestamp, event_id
                   ) AS previous_signature
              FROM institutional_inflection_timeline_events
        )
        SELECT COUNT(*)
          FROM ordered
         WHERE signature = previous_signature
    """)).scalar_one()
    current_target_rows = session.execute(
        select(InflectionSnapshotModel.snapshot_id).where(
            InflectionSnapshotModel.source_run_id == target_run
        )
    ).scalars().all()
    current_target_opportunities = session.execute(
        select(InstitutionalOpportunityModel.opportunity_id).where(
            InstitutionalOpportunityModel.stock_scanner_run_id == target_run
        )
    ).scalars().all()
    return {
        "version": "M68.2-INFLECTION-CLEANUP-1.0",
        "generated_at": now(),
        "mode": "PREFLIGHT",
        "target_materialized_stock_run": target_run,
        "target_stock_status": target.status,
        "target_stock_timestamp": target.snapshot_timestamp,
        "current_inflection_source_run": (
            None if inflection is None else inflection.source_run_id
        ),
        "target_inflection_rows_before": len(current_target_rows),
        "target_opportunities": len(current_target_opportunities),
        "rogue_unmaterialized_runs": int(rows["rogue_run_count"] or 0),
        "rogue_inflection_snapshots": int(rows["rogue_snapshot_count"] or 0),
        "rogue_timeline_events": int(rows["rogue_timeline_count"] or 0),
        "rogue_stock_publications": int(
            rows["rogue_stock_publication_count"] or 0
        ),
        "consecutive_duplicate_timeline_events": int(
            duplicate_timeline or 0
        ),
        "confirmation_required": CONFIRMATION,
        "safe_to_execute": True,
    }


def execute(session, preflight: dict) -> dict:
    target_run = preflight["target_materialized_stock_run"]
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
        {"name": "trading_ai:m68_inflection_authority"},
    )
    rogue_runs = [
        str(value)
        for value in session.execute(text("""
            SELECT DISTINCT i.source_run_id
              FROM institutional_inflection_snapshots i
             WHERE i.source_run_id <> :target_run
               AND NOT EXISTS (
                    SELECT 1
                      FROM institutional_option_opportunities o
                     WHERE o.stock_scanner_run_id = i.source_run_id
               )
             ORDER BY i.source_run_id
        """), {"target_run": target_run}).scalars().all()
    ]
    removed_timeline = 0
    removed_snapshots = 0
    removed_stock_publications = 0
    if rogue_runs:
        removed_timeline = session.execute(
            text("""
                DELETE FROM institutional_inflection_timeline_events
                 WHERE source_run_id = ANY(:run_ids)
            """), {"run_ids": rogue_runs}
        ).rowcount
        removed_snapshots = session.execute(
            text("""
                DELETE FROM institutional_inflection_snapshots
                 WHERE source_run_id = ANY(:run_ids)
            """), {"run_ids": rogue_runs}
        ).rowcount
        removed_stock_publications = session.execute(
            text("""
                DELETE FROM stock_scanner_publications
                 WHERE scanner_run_id = ANY(:run_ids)
                   AND NOT EXISTS (
                        SELECT 1
                          FROM institutional_option_opportunities o
                         WHERE o.stock_scanner_run_id =
                               stock_scanner_publications.scanner_run_id
                   )
            """), {"run_ids": rogue_runs}
        ).rowcount

    removed_duplicate_ids = session.execute(text("""
        WITH ordered AS (
            SELECT event_id,
                   COALESCE(payload_json::jsonb ->> 'direction', 'UNKNOWN')
                       || '|' || transition_state AS signature,
                   LAG(
                       COALESCE(payload_json::jsonb ->> 'direction', 'UNKNOWN')
                       || '|' || transition_state
                   ) OVER (
                       PARTITION BY symbol, timeframe
                       ORDER BY event_timestamp, event_id
                   ) AS previous_signature
              FROM institutional_inflection_timeline_events
        ), duplicates AS (
            SELECT event_id
              FROM ordered
             WHERE signature = previous_signature
        )
        DELETE FROM institutional_inflection_timeline_events t
         USING duplicates d
         WHERE t.event_id = d.event_id
        RETURNING t.event_id
    """)).scalars().all()
    session.commit()
    return {
        **preflight,
        "mode": "EXECUTED",
        "executed_at": now(),
        "rogue_run_ids": rogue_runs,
        "removed_rogue_timeline_events": int(removed_timeline or 0),
        "removed_rogue_inflection_snapshots": int(removed_snapshots or 0),
        "removed_rogue_stock_publications": int(
            removed_stock_publications or 0
        ),
        "removed_consecutive_duplicate_timeline_events": int(
            len(removed_duplicate_ids)
        ),
        "next_action": (
            "Run run_m68_2_recover_current_authority.py before restarting services"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight or execute bounded M68.2 lineage/timeline cleanup"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if args.execute and args.confirmation != CONFIRMATION:
        raise SystemExit(
            f"Execution requires --confirmation {CONFIRMATION}"
        )
    with SessionLocal() as session:
        payload = inspect(session)
        if args.execute:
            payload = execute(session, payload)
    _write(args.manifest, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
