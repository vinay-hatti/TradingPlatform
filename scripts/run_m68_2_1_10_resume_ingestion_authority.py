#!/usr/bin/env python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys

from sqlalchemy import desc, exists

from ingestion_split_common import (
    advance_institutional_options_workflow,
    materialize_institutional_options_opportunities,
)
from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.service import (
    InstitutionalInflectionService,
)
from trading_ai.institutional_options.advancement_authority import (
    AUTHORITY_KEY,
    AUTHORITY_VERSION,
    advancement_fingerprint,
    validate_current_advancement_authority,
)
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.opportunity_ingestion import (
    inspect_opportunity_lineage_resolution,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.stock_intelligence.models import (
    StockScannerCandidateModel,
    StockScannerPublicationModel,
)


VERSION = "M68.2.1.12-TERMINAL-LINEAGE-IDEMPOTENCE-1.0"
CONFIRMATION = "RESUME_M68_2_1_12_TERMINAL_LINEAGE_AUTHORITY"


def progress(stage: str, **details) -> None:
    print(json.dumps({
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "details": details,
    }, sort_keys=True, default=str), file=sys.stderr, flush=True)


def preflight() -> dict:
    with SessionLocal() as session:
        target = (
            session.query(StockScannerPublicationModel)
            .filter(
                StockScannerPublicationModel.publication_name
                == "current_stock_intelligence",
                StockScannerPublicationModel.status.in_(("READY", "DEGRADED")),
                exists().where(
                    StockScannerCandidateModel.scanner_run_id
                    == StockScannerPublicationModel.scanner_run_id
                ),
            )
            .order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
            .first()
        )
        if target is None:
            return {
                "version": VERSION,
                "mode": "PREFLIGHT",
                "safe_to_execute": False,
                "reason": "NO_CANDIDATE_BEARING_STOCK_PUBLICATION",
                "confirmation_required": CONFIRMATION,
            }
        target_run = str(target.scanner_run_id)
        candidates = (
            session.query(StockScannerCandidateModel)
            .filter_by(scanner_run_id=target_run)
            .count()
        )
        opportunities = (
            session.query(InstitutionalOpportunityModel)
            .filter_by(stock_scanner_run_id=target_run)
            .count()
        )
        marker = dict(
            (target.payload_json or {}).get(AUTHORITY_KEY) or {}
        )
        marker_fingerprint = str(marker.get("fingerprint") or "")
        current_fingerprint = ""
        if opportunities:
            current_fingerprint, _ = advancement_fingerprint(
                session, target_run
            )
        marker_valid = bool(
            opportunities
            and marker.get("version") == AUTHORITY_VERSION
            and marker.get("status") in {
                "COMPLETE",
                "COMPLETE_WITH_GOVERNED_EXCLUSIONS",
            }
            and str(marker.get("stock_scanner_run_id") or "")
            == target_run
            and marker_fingerprint == current_fingerprint
        )
        recovery_mode = (
            "MATERIALIZE_AND_ADVANCE"
            if opportunities == 0
            else "RESUME_PARTIAL_ADVANCEMENT"
        )
        older_orphan_rows = (
            session.query(StockScannerPublicationModel)
            .filter(
                StockScannerPublicationModel.publication_name
                == "current_stock_intelligence",
                StockScannerPublicationModel.scanner_run_id != target_run,
                StockScannerPublicationModel.status.in_(("READY", "DEGRADED")),
                exists().where(
                    StockScannerCandidateModel.scanner_run_id
                    == StockScannerPublicationModel.scanner_run_id
                ),
                ~exists().where(
                    InstitutionalOpportunityModel.stock_scanner_run_id
                    == StockScannerPublicationModel.scanner_run_id
                ),
            )
            .order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
            .all()
        )
        older_orphan_ids = [
            str(row.scanner_run_id) for row in older_orphan_rows
        ]
        lineage = dict((target.payload_json or {}).get("lineage") or {})
        opportunity_lineage_resolution = (
            inspect_opportunity_lineage_resolution(session, target_run)
        )
        lineage_safe = (
            opportunity_lineage_resolution.get("status") == "SAFE"
        )
        safe_to_execute = candidates > 0 and not marker_valid and lineage_safe
        reason = None
        if marker_valid:
            reason = "LATEST_AUTHORITY_ALREADY_COMPLETE"
        elif not lineage_safe:
            reason = "UNSAFE_OPPORTUNITY_LINEAGE"
        elif candidates <= 0:
            reason = "TARGET_HAS_NO_CANDIDATES"
        return {
            "version": VERSION,
            "mode": "PREFLIGHT",
            "safe_to_execute": safe_to_execute,
            "reason": reason,
            "confirmation_required": CONFIRMATION,
            "recovery_mode": recovery_mode,
            "target_stock_scanner_run_id": target_run,
            "target_stock_timestamp": target.snapshot_timestamp,
            "target_stock_status": target.status,
            "target_candidate_count": candidates,
            "target_opportunity_count": opportunities,
            "target_advancement_marker_status": marker.get("status"),
            "target_advancement_marker_valid": marker_valid,
            "target_advancement_fingerprint": current_fingerprint,
            "target_market_as_of_date": (
                lineage.get("market_as_of_date")
                or (target.payload_json or {}).get("market_as_of_date")
            ),
            "older_unmaterialized_publications_to_retire": len(
                older_orphan_ids
            ),
            "older_unmaterialized_stock_run_ids": older_orphan_ids,
            "opportunity_lineage_resolution": (
                opportunity_lineage_resolution
            ),
        }


def retire_older_orphans(
    target_run: str,
    orphan_run_ids: list[str],
) -> int:
    if not orphan_run_ids:
        return 0
    with SessionLocal() as session:
        rows = (
            session.query(StockScannerPublicationModel)
            .filter(
                StockScannerPublicationModel.publication_name
                == "current_stock_intelligence",
                StockScannerPublicationModel.scanner_run_id.in_(
                    tuple(orphan_run_ids)
                ),
                StockScannerPublicationModel.status.in_(("READY", "DEGRADED")),
                ~exists().where(
                    InstitutionalOpportunityModel.stock_scanner_run_id
                    == StockScannerPublicationModel.scanner_run_id
                ),
            )
            .all()
        )
        retired_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            payload = dict(row.payload_json or {})
            payload["authority_retirement"] = {
                "version": VERSION,
                "status": "RETIRED_UNMATERIALIZED",
                "retired_at": retired_at,
                "replacement_stock_scanner_run_id": target_run,
            }
            row.payload_json = payload
            row.status = "FAILED"
        session.commit()
        return len(rows)


def execute(args, manifest: dict) -> dict:
    target_run = str(manifest["target_stock_scanner_run_id"])
    progress("underlying_inflection_started", stock_scanner_run_id=target_run)
    underlying_inflection = InstitutionalInflectionService(SessionLocal).build(
        build_mode="UNDERLYING_PRIMARY"
    )
    if str(underlying_inflection.get("source_run_id") or "") != target_run:
        raise RuntimeError("Underlying Inflection recovered a different Stock run")

    progress(
        "opportunity_materialization_started",
        stock_scanner_run_id=target_run,
        recovery_mode=manifest.get("recovery_mode"),
        existing_opportunities=manifest.get("target_opportunity_count"),
    )
    # Materialization is continuity-key idempotent only after exact current
    # lineage owns identity across every lifecycle state.
    # Logical continuity is only a fallback for candidates without an exact
    # row; terminal exact rows and their downstream history remain immutable.
    materialization = materialize_institutional_options_opportunities(
        publication_name="current_stock_intelligence"
    )
    if str(materialization.get("stock_scanner_run_id") or "") != target_run:
        raise RuntimeError("Opportunity materialization recovered a different Stock run")
    if int(materialization.get("unsafe_logical_contentions") or 0) != 0:
        raise RuntimeError(
            "Opportunity materialization reported unsafe logical contentions"
        )
    expected_collisions = int(
        (
            manifest.get("opportunity_lineage_resolution") or {}
        ).get("lineage_collisions_prevented")
        or 0
    )
    actual_collisions = int(
        materialization.get("lineage_collisions_prevented") or 0
    )
    if actual_collisions != expected_collisions:
        raise RuntimeError(
            "Opportunity lineage changed after preflight: expected "
            f"{expected_collisions} prevented collisions, observed "
            f"{actual_collisions}"
        )
    progress(
        "opportunity_materialization_completed",
        stock_scanner_run_id=target_run,
        exact_current_lineage_rows=materialization.get(
            "exact_current_lineage_rows", 0
        ),
        terminal_exact_preserved=materialization.get(
            "terminal_exact_preserved", 0
        ),
        lineage_collisions_prevented=actual_collisions,
    )

    progress("options_inflection_started", stock_scanner_run_id=target_run)
    options_inflection = InstitutionalInflectionService(SessionLocal).build(
        build_mode="OPTIONS_ENRICHMENT"
    )
    if str(options_inflection.get("source_run_id") or "") != target_run:
        raise RuntimeError("Options Inflection recovered a different Stock run")

    progress("institutional_options_advancement_started", stock_scanner_run_id=target_run)
    advancement = advance_institutional_options_workflow(
        run_strategies=True,
        run_contracts=True,
        run_decisions=True,
        run_option_valuation=True,
        require_option_valuation=True,
        require_success=True,
        require_complete=False,
    )
    authority = validate_current_advancement_authority(SessionLocal)
    if authority["stock_scanner_run_id"] != target_run:
        raise RuntimeError("Advancement authority recovered a different Stock run")

    retired = retire_older_orphans(
        target_run,
        list(manifest.get("older_unmaterialized_stock_run_ids") or ()),
    )
    progress(
        "m64_authoritative_cycle_started",
        stock_scanner_run_id=target_run,
        portfolio_id=args.portfolio_id,
    )
    m64 = Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(
        args.portfolio_id,
        # Supersedes actor m68-2-1-10-resumable-controlled-recovery.
        actor="m68-2-1-12-terminal-lineage-controlled-recovery",
        lock_timeout_seconds=5.0,
        progress=lambda stage, details: progress(
            f"m64_{stage}", **details
        ),
    )
    if str(m64.get("stock_scanner_run_id") or "") != target_run:
        raise RuntimeError("M64 published a different Stock run")
    return {
        **manifest,
        "mode": "EXECUTED",
        "status": "PASSED",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "underlying_inflection": underlying_inflection,
        "options_inflection": options_inflection,
        "materialization": materialization,
        "institutional_options_advancement": advancement,
        "institutional_options_authority": authority,
        "older_unmaterialized_publications_retired": retired,
        "m64": m64,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resume ingestion authority with terminal exact-lineage "
            "idempotence"
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    manifest = preflight()
    if not args.execute:
        output = manifest
    elif args.confirmation != CONFIRMATION:
        output = {
            **manifest,
            "mode": "REFUSED",
            "status": "FAILED",
            "error": "EXACT_CONFIRMATION_REQUIRED",
        }
    elif not manifest.get("safe_to_execute"):
        output = {
            **manifest,
            "mode": "REFUSED",
            "status": "FAILED",
            "error": "PREFLIGHT_NOT_SAFE",
        }
    else:
        try:
            output = execute(args, manifest)
        except Exception as exc:
            progress("recovery_failed", error_type=type(exc).__name__, error=str(exc))
            output = {
                **manifest,
                "mode": "FAILED",
                "status": "FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            }
    encoded = json.dumps(output, indent=2, sort_keys=True, default=str)
    print(encoded)
    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
    if not args.execute:
        return 0 if manifest.get("safe_to_execute") else 2
    return 0 if output.get("status") == "PASSED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
