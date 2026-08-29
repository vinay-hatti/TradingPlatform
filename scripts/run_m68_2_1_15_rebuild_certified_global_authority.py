#!/usr/bin/env python
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import desc, text

from ingestion_split_common import advance_institutional_options_workflow
from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.opportunity_ingestion import (
    InstitutionalOpportunityIngestionService,
    StockOpportunityEligibilityService,
)
from trading_ai.institutional_options.publication_scope import (
    latest_published_stock_scanner_run_id,
)
from trading_ai.institutional_options.trade_builder_authority import (
    readiness_integrity_report,
)
from trading_ai.portfolio_risk_allocation.models import (
    PortfolioIntelligencePublicationModel,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.stock_intelligence.models import StockScannerCandidateModel


VERSION = "M68.2.1.15.3-CERTIFIED-GLOBAL-AUTHORITY-RECOVERY-1.0"
CONFIRMATION = "REBUILD_M68_2_1_15_CERTIFIED_GLOBAL_AUTHORITY"
CONSTRAINT = "ck_m62_ready_requires_final_certification"


def progress(stage: str, details: dict) -> None:
    print(json.dumps({
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "details": details,
    }, sort_keys=True, default=str), file=sys.stderr, flush=True)


def source_eligibility(session, stock_run_id: str) -> dict:
    rows = (
        session.query(StockScannerCandidateModel)
        .filter_by(scanner_run_id=stock_run_id)
        .order_by(StockScannerCandidateModel.symbol)
        .all()
    )
    service = StockOpportunityEligibilityService()
    reason_counts: Counter[str] = Counter()
    eligible = 0
    for row in rows:
        snapshot_timestamp = row.snapshot_timestamp
        if hasattr(snapshot_timestamp, "isoformat"):
            snapshot_timestamp = snapshot_timestamp.isoformat()
        decision = service.evaluate(
            dict(row.payload_json or {}),
            snapshot_timestamp=snapshot_timestamp,
        )
        if decision.eligible:
            eligible += 1
        reason_counts.update(decision.reasons)
    return {
        "source_candidate_count": len(rows),
        "source_eligible_count": eligible,
        "source_ineligible_count": len(rows) - eligible,
        "source_ineligibility_reason_counts": dict(sorted(reason_counts.items())),
    }


def preflight() -> dict:
    with SessionLocal() as session:
        # Recovery owns materialization, so its source must be the newest
        # published Stock Intelligence authority even when that run has zero
        # opportunity rows. Selecting the latest *already materialized* run
        # would silently recover yesterday's authority again.
        stock_run_id = latest_published_stock_scanner_run_id(session)
        if not stock_run_id:
            return {
                "version": VERSION,
                "mode": "PREFLIGHT",
                "safe_to_execute": False,
                "reason": "NO_MATERIALIZED_STOCK_AUTHORITY",
                "confirmation_required": CONFIRMATION,
            }
        source = source_eligibility(session, stock_run_id)
        opportunities = (
            session.query(InstitutionalOpportunityModel)
            .filter_by(stock_scanner_run_id=stock_run_id)
            .all()
        )
        states = Counter(str(row.state) for row in opportunities)
        integrity = readiness_integrity_report(
            session,
            stock_scanner_run_id=stock_run_id,
        )
        return {
            "version": VERSION,
            "mode": "PREFLIGHT",
            "safe_to_execute": bool(source["source_candidate_count"]),
            "reason": None if source["source_candidate_count"] else (
                "CURRENT_AUTHORITY_HAS_NO_SOURCE_CANDIDATES"
            ),
            "confirmation_required": CONFIRMATION,
            "stock_scanner_run_id": stock_run_id,
            **source,
            "materialized_opportunity_count": len(opportunities),
            "opportunity_states": dict(sorted(states.items())),
            "readiness_integrity": integrity,
        }


def reconcile_historical_ready_flags() -> int:
    """Fail-close every legacy true flag that lacks the required certificate."""

    with SessionLocal() as session:
        result = session.execute(text("""
            UPDATE institutional_option_execution_recommendations
               SET ready_for_trade_builder = false,
                   payload_json = jsonb_set(
                       jsonb_set(
                           payload_json::jsonb,
                           '{trade_plan_certification,execution_disposition}',
                           to_jsonb(
                               'INVALIDATED_LEGACY_READINESS'::text
                           ),
                           true
                       ),
                       '{trade_plan_certification,trade_builder_ready}',
                       'false'::jsonb,
                       true
                   )
             WHERE ready_for_trade_builder = true
               AND NOT ((
                   payload_json::jsonb #>>
                     '{trade_plan_certification,status}' = 'PASS'
                   AND payload_json::jsonb #>>
                     '{trade_plan_certification,certification_scope}'
                       = 'INSTITUTIONAL_OPTIONS_FINAL_PLAN'
                   AND payload_json::jsonb #>>
                     '{trade_plan_certification,execution_disposition}'
                       = 'READY_NOW'
                   AND payload_json::jsonb #>>
                     '{trade_plan_certification,trade_builder_ready}'
                       = 'true'
               ) IS TRUE)
        """))
        changed = int(result.rowcount or 0)
        session.commit()
        return changed


def execute(manifest: dict) -> dict:
    stock_run_id = str(manifest["stock_scanner_run_id"])
    reconciled_flags = reconcile_historical_ready_flags()
    progress("legacy_false_ready_flags_reconciled", {
        "updated": reconciled_flags,
    })

    with SessionLocal() as session:
        ingestion = InstitutionalOpportunityIngestionService(session).ingest(
            limit=None,
            actor="m68.2.1.15-full-universe-recovery",
        )
        session.commit()
        ingestion_payload = asdict(ingestion)
    progress("full_source_universe_ingested", ingestion_payload)
    if str(ingestion.stock_scanner_run_id) != stock_run_id:
        raise RuntimeError(
            "Stock authority changed during recovery: expected "
            f"{stock_run_id}, observed {ingestion.stock_scanner_run_id}"
        )
    if ingestion.requested != manifest["source_candidate_count"]:
        raise RuntimeError(
            "Full-universe ingestion coverage changed during recovery: "
            f"expected={manifest['source_candidate_count']} "
            f"observed={ingestion.requested}"
        )

    advancement = advance_institutional_options_workflow(
        run_strategies=True,
        run_contracts=True,
        run_decisions=True,
        run_option_valuation=True,
        require_option_valuation=True,
        require_success=True,
        require_complete=False,
    )
    progress("institutional_options_advancement_completed", {
        "status": advancement.get("status"),
        "summary": advancement.get("summary"),
        "stages": advancement.get("stages"),
    })

    with SessionLocal() as session:
        integrity = readiness_integrity_report(
            session,
            stock_scanner_run_id=stock_run_id,
        )
    if integrity["invalid_readiness_count"]:
        raise RuntimeError(
            "Institutional Options rebuild left invalid readiness rows: "
            + json.dumps(integrity, sort_keys=True, default=str)
        )

    m64 = Milestone64ContinuousPortfolioIntelligenceService(
        SessionLocal
    ).run(
        "PAPER-PRIMARY",
        actor="m68.2.1.15-certified-global-recovery",
        skip_unchanged_authority=False,
        lock_timeout_seconds=30.0,
        progress=progress,
    )

    with SessionLocal() as session:
        publication = (
            session.query(PortfolioIntelligencePublicationModel)
            .filter_by(
                portfolio_id="PAPER-PRIMARY",
                publication_name="current_portfolio_allocation",
            )
            .order_by(desc(PortfolioIntelligencePublicationModel.published_at))
            .first()
        )
        if publication is None:
            raise RuntimeError("M64 current portfolio publication is missing")
        payload = dict(publication.payload_json or {})
        global_authority = dict(payload.get("global_candidate_authority") or {})
        proof = dict(payload.get("optimization_proof") or {})
        if (
            global_authority.get("status") != "PROVEN"
            or global_authority.get("all_source_candidates_classified") is not True
            or global_authority.get("invalid_ready_invariant_count") != 0
            or global_authority.get("source_universe_count")
                != manifest["source_candidate_count"]
            or proof.get("optimality_proven") is not True
        ):
            raise RuntimeError(
                "M64 publication did not prove certified full-universe authority"
            )
        session.execute(text(f"""
            ALTER TABLE institutional_option_execution_recommendations
            VALIDATE CONSTRAINT {CONSTRAINT}
        """))
        session.commit()
        publication_id = publication.publication_id
        optimization_snapshot_id = publication.optimization_snapshot_id

    return {
        "version": VERSION,
        "mode": "EXECUTED",
        "status": "PASSED",
        "stock_scanner_run_id": stock_run_id,
        "legacy_false_ready_flags_reconciled": reconciled_flags,
        "source_ingestion": ingestion_payload,
        "institutional_options_advancement": advancement,
        "readiness_integrity": integrity,
        "m64_cycle": m64,
        "publication_id": publication_id,
        "optimization_snapshot_id": optimization_snapshot_id,
        "global_candidate_authority": global_authority,
        "optimization_proof": proof,
        "database_constraint_validated": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    manifest = preflight()
    try:
        if args.execute:
            if args.confirmation != CONFIRMATION:
                raise ValueError(
                    f"--confirmation must equal {CONFIRMATION}"
                )
            if not manifest.get("safe_to_execute"):
                raise RuntimeError(
                    "Preflight is not safe: "
                    + str(manifest.get("reason"))
                )
            manifest = execute(manifest)
    except Exception as exc:
        manifest = {
            **manifest,
            "mode": "EXECUTION_FAILED" if args.execute else "PREFLIGHT_FAILED",
            "status": "FAILED",
            "failure": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
        rendered = json.dumps(
            manifest, indent=2, sort_keys=True, default=str
        )
        if args.manifest:
            Path(args.manifest).write_text(
                rendered + "\n", encoding="utf-8"
            )
        print(rendered)
        progress("recovery_failed", manifest["failure"])
        raise
    else:
        rendered = json.dumps(
            manifest, indent=2, sort_keys=True, default=str
        )
        if args.manifest:
            Path(args.manifest).write_text(
                rendered + "\n", encoding="utf-8"
            )
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
