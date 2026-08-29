#!/usr/bin/env python
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import sys

from sqlalchemy import desc

from ingestion_split_common import advance_institutional_options_workflow
from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.publication_scope import (
    latest_stock_scanner_run_id,
)
from trading_ai.portfolio_risk_allocation.config import (
    load_portfolio_optimizer_config,
)
from trading_ai.portfolio_risk_allocation.models import (
    PortfolioIntelligencePublicationModel,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.stock_intelligence.models import StockScannerCandidateModel


VERSION = "M68.2.1.13-GLOBAL-FEASIBLE-RECOVERY-1.0"
CONFIRMATION = "REBUILD_M68_2_1_13_GLOBAL_FEASIBLE_AUTHORITY"


def progress(stage: str, details: dict) -> None:
    print(json.dumps({
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "details": details,
    }, sort_keys=True, default=str), file=sys.stderr, flush=True)


def preflight() -> dict:
    runtime = load_portfolio_optimizer_config()
    with SessionLocal() as session:
        stock_run_id = latest_stock_scanner_run_id(session)
        if not stock_run_id:
            return {
                "version": VERSION,
                "mode": "PREFLIGHT",
                "safe_to_execute": False,
                "reason": "NO_MATERIALIZED_STOCK_AUTHORITY",
                "confirmation_required": CONFIRMATION,
            }
        source_count = (
            session.query(StockScannerCandidateModel)
            .filter_by(scanner_run_id=stock_run_id)
            .count()
        )
        opportunities = (
            session.query(InstitutionalOpportunityModel)
            .filter_by(stock_scanner_run_id=stock_run_id)
            .all()
        )
        states = Counter(str(row.state) for row in opportunities)
        return {
            "version": VERSION,
            "mode": "PREFLIGHT",
            "safe_to_execute": bool(source_count and opportunities),
            "reason": None if source_count and opportunities else (
                "CURRENT_AUTHORITY_HAS_NO_OPPORTUNITIES"
            ),
            "confirmation_required": CONFIRMATION,
            "stock_scanner_run_id": stock_run_id,
            "source_candidate_count": source_count,
            "opportunity_count": len(opportunities),
            "opportunity_states": dict(sorted(states.items())),
            "max_new_positions": runtime.max_new_positions,
            "max_new_positions_source": runtime.source,
        }


def execute(manifest: dict) -> dict:
    progress("institutional_options_advancement_started", {
        "stock_scanner_run_id": manifest["stock_scanner_run_id"],
    })
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
    })
    m64 = Milestone64ContinuousPortfolioIntelligenceService(
        SessionLocal
    ).run(
        "PAPER-PRIMARY",
        actor="m68-2-1-13-global-feasible-recovery",
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
            .order_by(
                desc(PortfolioIntelligencePublicationModel.published_at)
            )
            .first()
        )
        if publication is None:
            raise RuntimeError("M64 current portfolio publication is missing")
        payload = dict(publication.payload_json or {})
        global_authority = dict(
            payload.get("global_candidate_authority") or {}
        )
        proof = dict(payload.get("optimization_proof") or {})
        if (
            global_authority.get("status") != "PROVEN"
            or global_authority.get("all_source_candidates_classified")
            is not True
            or proof.get("optimality_proven") is not True
        ):
            raise RuntimeError(
                "M64 publication did not prove complete global feasible authority"
            )
        return {
            "version": VERSION,
            "mode": "EXECUTED",
            "status": "PASSED",
            "institutional_options_advancement": advancement,
            "m64_cycle": m64,
            "publication_id": publication.publication_id,
            "optimization_snapshot_id": publication.optimization_snapshot_id,
            "global_candidate_authority": {
                key: value for key, value in global_authority.items()
                if key != "candidate_ledger"
            },
            "optimization_proof": proof,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild M68.2.1.13/M64 global feasible authority"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    manifest = preflight()
    if args.execute:
        if args.confirmation != CONFIRMATION:
            raise SystemExit(
                f"Refused: --confirmation must equal {CONFIRMATION}"
            )
        if not manifest.get("safe_to_execute"):
            raise SystemExit(
                "Refused: preflight is not safe: "
                + str(manifest.get("reason"))
            )
        manifest = execute(manifest)
    rendered = json.dumps(manifest, indent=2, sort_keys=True, default=str)
    if args.manifest:
        from pathlib import Path
        Path(args.manifest).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
