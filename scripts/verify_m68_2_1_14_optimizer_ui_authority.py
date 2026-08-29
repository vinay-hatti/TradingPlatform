#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


VERSION = "M68.2.1.14.1-CURRENT-UI-COMPATIBILITY-VERIFICATION-1.0"


def source_checks(root: Path) -> dict[str, bool]:
    config = (
        root / "src/trading_ai/portfolio_risk_allocation/config.py"
    ).read_text(encoding="utf-8")
    optimizer = (
        root / "src/trading_ai/portfolio_risk_allocation/optimizer.py"
    ).read_text(encoding="utf-8")
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text(encoding="utf-8")
    handoff = (
        root / "src/trading_ai/institutional_options/handoff.py"
    ).read_text(encoding="utf-8")
    page = (
        root / "ui/workstation/src/InstitutionalOptionsPage.tsx"
    ).read_text(encoding="utf-8")
    recovery = (
        root
        / "scripts/run_m68_2_1_14_rebuild_optimizer_ui_authority.py"
    ).read_text(encoding="utf-8")

    return {
        "dotenv_cap_range_is_1_to_100": (
            'MAX_NEW_POSITIONS_MAX = 100' in config
            and 'MAX_NEW_POSITIONS_MIN = 1' in config
            and 'value <= MAX_NEW_POSITIONS_MAX' in config
        ),
        "optimizer_uses_shared_cap_bounds": (
            "MAX_NEW_POSITIONS_MAX" in optimizer
            and "MAX_NEW_POSITIONS_MIN" in optimizer
            and "M64.2.4.9-GLOBAL-FEASIBLE-OPTIMIZER" in optimizer
        ),
        "policy_change_invalidates_authority": (
            "PortfolioOptimizationService.resolved_policy()" in orchestration
            and "M64.2.4.9-GLOBAL-FEASIBLE-CYCLE" in orchestration
        ),
        "ui_reads_optimizer_selection": (
            "function tradeBuilderAuthority" in page
            and "optimizer.optimality_proven===true" in page
            and "optimizer.selected===true" in page
            and "optimizer.selected===false" in page
        ),
        "ui_requires_selected_global_feasible": (
            "optimizer.status==='SELECTED_GLOBAL_FEASIBLE'" in page
            and "const handoffReady=tradeBuilder.authorized" in page
            and "disabled={!handoffReady||!!busy}" in page
        ),
        "ui_explains_not_selected": (
            "NOT_SELECTED_GLOBAL_FEASIBLE" in page
            and "No Trade Builder handoff is authorized" in page
        ),
        "ui_explains_stale_authority": (
            "OPTIMIZER_AUTHORITY_MISSING" in page
            and "Rebuild portfolio authority" in page
        ),
        "conditional_entry_governance_preserved": (
            "ENTRY_NOT_READY" in page
            and "finalCert.execution_disposition" in page
            and "finalCert.entry_execution?.reason_codes" in page
            and "Governed plan is waiting for its entry" in page
            and "global portfolio selection are governed separately" in page
        ),
        "static_ready_message_removed": (
            "Review the decision and open it in Trade Builder." not in page
        ),
        "backend_and_ui_share_selection_contract": (
            "SELECTED_GLOBAL_FEASIBLE" in handoff
            and "optimality_proven" in handoff
            and "SELECTED_GLOBAL_FEASIBLE" in page
            and "optimalityProven" in page
        ),
        "controlled_rebuild_available": (
            "REBUILD_M68_2_1_14_OPTIMIZER_UI_AUTHORITY" in recovery
            and "require_success=True" in recovery
        ),
    }


def runtime_checks() -> tuple[dict[str, bool], dict]:
    from trading_ai.database.session import SessionLocal
    from trading_ai.institutional_options.models import (
        InstitutionalDecisionSnapshotModel,
        InstitutionalOpportunityModel,
    )
    from trading_ai.portfolio_risk_allocation.config import (
        MAX_NEW_POSITIONS_MAX,
        load_portfolio_optimizer_config,
    )
    from trading_ai.portfolio_risk_allocation.models import (
        PortfolioIntelligencePublicationModel,
    )

    runtime = load_portfolio_optimizer_config()
    with SessionLocal() as session:
        publication = (
            session.query(PortfolioIntelligencePublicationModel)
            .filter_by(
                portfolio_id="PAPER-PRIMARY",
                publication_name="current_portfolio_allocation",
            )
            .one_or_none()
        )
        publication_payload = (
            dict(publication.payload_json or {}) if publication else {}
        )
        stock_run = publication_payload.get("stock_scanner_run_id")
        ready = (
            session.query(InstitutionalOpportunityModel)
            .filter_by(
                stock_scanner_run_id=stock_run,
                state="READY_FOR_EXECUTION",
            )
            .all()
            if stock_run
            else []
        )
        decision_rows = (
            session.query(InstitutionalDecisionSnapshotModel)
            .filter(
                InstitutionalDecisionSnapshotModel.opportunity_id.in_(
                    [row.opportunity_id for row in ready]
                )
            )
            .all()
            if ready
            else []
        )

    selections = []
    for row in decision_rows:
        portfolio = dict(
            (dict(row.payload_json or {}).get("portfolio_decision") or {})
        )
        selections.append(dict(portfolio.get("optimizer_selection") or {}))
    selected = [item for item in selections if item.get("selected") is True]
    not_selected = [
        item for item in selections if item.get("selected") is False
    ]
    policy = dict(publication_payload.get("resolved_optimizer_policy") or {})
    checks = {
        "runtime_publication_exists": publication is not None,
        "runtime_env_cap_is_100": runtime.max_new_positions == 100,
        "runtime_env_cap_within_governed_range": (
            1 <= runtime.max_new_positions <= MAX_NEW_POSITIONS_MAX
        ),
        "runtime_policy_matches_env": (
            int(policy.get("max_new_positions") or 0)
            == runtime.max_new_positions
        ),
        "runtime_ready_coverage_complete": len(selections) == len(ready),
        "runtime_all_optimizer_decisions_proven": (
            bool(selections)
            and all(item.get("optimality_proven") is True for item in selections)
        ),
        "runtime_selection_statuses_complete": (
            len(selected) + len(not_selected) == len(ready)
            and all(
                item.get("status") == "SELECTED_GLOBAL_FEASIBLE"
                for item in selected
            )
            and all(
                item.get("status") == "NOT_SELECTED_GLOBAL_FEASIBLE"
                for item in not_selected
            )
        ),
    }
    details = {
        "publication_id": (
            None if publication is None else publication.publication_id
        ),
        "stock_scanner_run_id": stock_run,
        "ready_for_execution_count": len(ready),
        "selected_global_feasible_count": len(selected),
        "not_selected_global_feasible_count": len(not_selected),
        "max_new_positions": runtime.max_new_positions,
        "max_new_positions_source": runtime.source,
    }
    return checks, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    checks = source_checks(Path(args.root).resolve())
    details = {}
    if args.runtime:
        runtime, details = runtime_checks()
        checks.update(runtime)
    passed = all(checks.values())
    print(
        json.dumps(
            {
                "version": VERSION,
                "status": "PASSED" if passed else "FAILED",
                "checks": checks,
                "details": details,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
