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
    validate_current_advancement_authority,
)
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.stock_intelligence.models import (
    StockScannerCandidateModel,
    StockScannerPublicationModel,
)


VERSION = "M68.2.1.8-INGESTION-AUTHORITY-RECOVERY-1.0"
CONFIRMATION = "RECOVER_M68_2_1_8_INGESTION_AUTHORITY"


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
                ~exists().where(
                    InstitutionalOpportunityModel.stock_scanner_run_id
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
                "reason": "NO_RECOVERABLE_UNMATERIALIZED_STOCK_PUBLICATION",
                "confirmation_required": CONFIRMATION,
            }
        target_run = str(target.scanner_run_id)
        candidates = (
            session.query(StockScannerCandidateModel)
            .filter_by(scanner_run_id=target_run)
            .count()
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
        return {
            "version": VERSION,
            "mode": "PREFLIGHT",
            "safe_to_execute": candidates > 0,
            "confirmation_required": CONFIRMATION,
            "target_stock_scanner_run_id": target_run,
            "target_stock_timestamp": target.snapshot_timestamp,
            "target_stock_status": target.status,
            "target_candidate_count": candidates,
            "target_market_as_of_date": (
                lineage.get("market_as_of_date")
                or (target.payload_json or {}).get("market_as_of_date")
            ),
            "older_unmaterialized_publications_to_retire": len(
                older_orphan_ids
            ),
            "older_unmaterialized_stock_run_ids": older_orphan_ids,
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

    progress("opportunity_materialization_started", stock_scanner_run_id=target_run)
    materialization = materialize_institutional_options_opportunities(
        publication_name="current_stock_intelligence"
    )
    if str(materialization.get("stock_scanner_run_id") or "") != target_run:
        raise RuntimeError("Opportunity materialization recovered a different Stock run")

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
        actor="m68-2-1-8-controlled-recovery",
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
        description="Recover the failed M68.2.1.8 ingestion authority chain"
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
