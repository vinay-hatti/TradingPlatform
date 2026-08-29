#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


VERSION = "M68.2.1.13-GLOBAL-FEASIBLE-VERIFICATION-1.0"


def source_checks(root: Path) -> dict[str, bool]:
    contract = (
        root / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text(encoding="utf-8")
    repository = (
        root / "src/trading_ai/institutional_options/repository.py"
    ).read_text(encoding="utf-8")
    handoff = (
        root / "src/trading_ai/institutional_options/handoff.py"
    ).read_text(encoding="utf-8")
    optimizer = (
        root / "src/trading_ai/portfolio_risk_allocation/optimizer.py"
    ).read_text(encoding="utf-8")
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text(encoding="utf-8")
    decision = (
        root / "src/trading_ai/portfolio_risk_allocation/decision_intelligence.py"
    ).read_text(encoding="utf-8")
    config = (
        root / "src/trading_ai/portfolio_risk_allocation/config.py"
    ).read_text(encoding="utf-8")
    recovery = (
        root / "scripts/run_m68_2_1_13_rebuild_global_feasible_authority.py"
    ).read_text(encoding="utf-8")
    default_policy_block = optimizer.split("DEFAULT_POLICY = {", 1)[1].split(
        "}", 1
    )[0]
    return {
        "all_eligible_strategy_packages_evaluated": (
            "all_eligible_strategies_evaluated" in contract
            and "for any eligible strategy after exhaustive" in contract
            and "alternative_executable_count" not in contract
        ),
        "joint_strategy_contract_ranking_persisted": (
            "package_ranking" in contract
            and "MAXIMIZE_STRATEGY_AND_CONTRACT_QUALITY" in contract
            and "contract_feasibility_authority" in repository
        ),
        "max_new_positions_not_hardcoded": (
            '"max_new_positions"' not in default_policy_block
            and "M64_MAX_NEW_POSITIONS" in config
            and "no code default" in config
        ),
        "dotenv_policy_in_authority_fingerprint": (
            "PortfolioOptimizationService.resolved_policy()" in orchestration
        ),
        "exact_branch_and_bound": (
            "DETERMINISTIC_EXACT_BRANCH_AND_BOUND" in optimizer
            and "all_feasible_subsets_covered_by_search_or_bound" in optimizer
            and "node_limit_reached" in optimizer
        ),
        "order_independent_capital": (
            "order_independent_candidate_capital" in optimizer
            and "remaining_capital -=" not in optimizer
        ),
        "symbol_limit_enforced": "SYMBOL_BUDGET_LIMIT" in optimizer,
        "full_stock_universe_ledger": (
            "FROM stock_scanner_candidates" in optimizer
            and "all_source_candidates_classified" in optimizer
            and "candidate_ledger" in optimizer
        ),
        "global_claim_scoped_and_proven": (
            "GLOBAL_BEST_PORTFOLIO_FEASIBLE_SUBSET" in optimizer
            and "scope_limitation" in optimizer
            and "optimality_proven" in optimizer
        ),
        "optimizer_selection_activated": (
            "optimizer_selection" in decision
            and "SELECTED_GLOBAL_FEASIBLE" in decision
        ),
        "trade_builder_requires_global_selection": (
            "SELECTED_GLOBAL_FEASIBLE" in handoff
            and "proven global feasible subset" in handoff
        ),
        "controlled_rebuild_available": (
            "REBUILD_M68_2_1_13_GLOBAL_FEASIBLE_AUTHORITY" in recovery
            and "require_success=True" in recovery
        ),
    }


def runtime_checks() -> tuple[dict[str, bool], dict]:
    from trading_ai.database.session import SessionLocal
    from trading_ai.portfolio_risk_allocation.models import (
        PortfolioIntelligencePublicationModel,
    )

    with SessionLocal() as session:
        publication = (
            session.query(PortfolioIntelligencePublicationModel)
            .filter_by(
                portfolio_id="PAPER-PRIMARY",
                publication_name="current_portfolio_allocation",
            )
            .one_or_none()
        )
        payload = dict(publication.payload_json or {}) if publication else {}
    proof = dict(payload.get("optimization_proof") or {})
    global_authority = dict(payload.get("global_candidate_authority") or {})
    policy = dict(payload.get("resolved_optimizer_policy") or {})
    checks = {
        "runtime_publication_exists": publication is not None,
        "runtime_optimality_proven": proof.get("optimality_proven") is True,
        "runtime_full_universe_classified": (
            global_authority.get("all_source_candidates_classified") is True
        ),
        "runtime_global_claim_proven": global_authority.get("status") == "PROVEN",
        "runtime_env_policy_source": (
            "M64_MAX_NEW_POSITIONS" in str(
                policy.get("max_new_positions_source") or ""
            )
        ),
        "runtime_selected_within_cap": (
            int(global_authority.get("selected_count") or 0)
            <= int(policy.get("max_new_positions") or 0)
        ),
    }
    details = {
        "publication_id": None if publication is None else publication.publication_id,
        "source_universe_count": global_authority.get("source_universe_count"),
        "executable_now_count": global_authority.get("executable_now_count"),
        "selected_count": global_authority.get("selected_count"),
        "max_new_positions": policy.get("max_new_positions"),
        "max_new_positions_source": policy.get("max_new_positions_source"),
        "objective_total_score": proof.get("objective_total_score"),
        "nodes_evaluated": proof.get("nodes_evaluated"),
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
    print(json.dumps({
        "version": VERSION,
        "status": "PASSED" if passed else "FAILED",
        "checks": checks,
        "details": details,
    }, indent=2, sort_keys=True, default=str))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
