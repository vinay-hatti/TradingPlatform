from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.service import InstitutionalInflectionService
from trading_ai.institutional_options.contract_optimization import (
    InstitutionalContractOptimizationService,
)
from trading_ai.institutional_options.management import (
    InstitutionalDynamicManagementService,
)
from trading_ai.institutional_options.models import InstitutionalOpportunityModel
from trading_ai.institutional_options.repository import (
    InstitutionalOpportunityRepository,
)


GOVERNED_CONTRACT_UNAVAILABLE_MARKERS = (
    "ValueError: No executable contract recommendation generated",
    "LookupError: No persisted Polygon option data found",
    "LookupError: No underlying price found",
)


def _optimizer_error_opportunity_id(error: str) -> str:
    return str(error).split(":", 1)[0].strip()


def _governed_contract_unavailable(error: str) -> bool:
    return any(
        marker in str(error)
        for marker in GOVERNED_CONTRACT_UNAVAILABLE_MARKERS
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild M68.2 against the latest materialized Stock authority"
    )
    parser.add_argument("--timeframe", default="1d", choices=("1d", "1w", "1mo"))
    args = parser.parse_args()
    result = InstitutionalInflectionService(SessionLocal).build(
        timeframe=args.timeframe,
        build_mode="OPTIONS_ENRICHMENT",
    )
    source_run_id = str(result.get("source_run_id") or "")
    management_payload: dict = {}
    contract_regeneration_payload: dict = {
        "requested": 0,
        "optimized": 0,
        "failed": 0,
        "executable_recommendations": 0,
        "non_executable_recommendations": 0,
        "errors": (),
        "governed_unavailable": 0,
        "governed_unavailable_opportunity_ids": (),
        "unexpected_failures": 0,
        "unexpected_errors": (),
    }
    post_regeneration_payload: dict = {
        "requested": 0,
        "created": 0,
        "failed": 0,
        "certified": 0,
        "rejected": 0,
        "waiting_for_entry": 0,
        "regenerate_required": 0,
        "contract_regeneration_required": 0,
        "contract_regeneration_opportunity_ids": (),
        "errors": (),
    }
    state_counts: dict[str, int] = {}
    integrity: dict[str, int] = {}
    resumed_pending_contract_regeneration_ids: tuple[str, ...] = ()
    with SessionLocal() as session:
        resumed_pending_contract_regeneration_ids = tuple(
            str(value)
            for value in session.execute(text("""
                SELECT o.opportunity_id
                  FROM institutional_option_opportunities o
                 WHERE o.stock_scanner_run_id = :source_run_id
                   AND o.state = 'STRATEGIES_GENERATED'
                   AND COALESCE(
                       (o.payload_json::jsonb #>>
                         '{metadata,m68_2_1_3_contract_regeneration_required}')::boolean,
                       false
                   )
                 ORDER BY o.opportunity_id
            """), {"source_run_id": source_run_id}).scalars().all()
        )
        opportunity_ids = [
            str(row.opportunity_id)
            for row in session.query(InstitutionalOpportunityModel).filter(
                InstitutionalOpportunityModel.stock_scanner_run_id
                == source_run_id,
                InstitutionalOpportunityModel.state.in_((
                    "CONTRACTS_OPTIMIZED", "READY_FOR_EXECUTION",
                )),
            ).all()
        ]
        management = InstitutionalDynamicManagementService(session).generate(
            opportunity_ids=opportunity_ids,
        )
        management_payload = management.__dict__
        regeneration_ids = tuple(dict.fromkeys((
            *resumed_pending_contract_regeneration_ids,
            *management.contract_regeneration_opportunity_ids,
        )))
        if regeneration_ids:
            contract_regeneration = (
                InstitutionalContractOptimizationService(session).optimize(
                    opportunity_ids=list(regeneration_ids),
                )
            )
            contract_regeneration_payload = contract_regeneration.__dict__
            governed_errors = tuple(
                error for error in contract_regeneration.errors
                if _governed_contract_unavailable(error)
            )
            unexpected_errors = tuple(
                error for error in contract_regeneration.errors
                if not _governed_contract_unavailable(error)
            )
            governed_unavailable_ids = tuple(
                _optimizer_error_opportunity_id(error)
                for error in governed_errors
            )
            repository = InstitutionalOpportunityRepository(session)
            for error in governed_errors:
                repository.resolve_contract_regeneration_unavailable(
                    _optimizer_error_opportunity_id(error),
                    reason=(
                        "Current Polygon chain produced no executable exact "
                        f"package: {error}"
                    ),
                )
            contract_regeneration_payload.update({
                "governed_unavailable": len(governed_unavailable_ids),
                "governed_unavailable_opportunity_ids": (
                    governed_unavailable_ids
                ),
                "unexpected_failures": len(unexpected_errors),
                "unexpected_errors": unexpected_errors,
            })
            post_regeneration_ids = tuple(
                str(row.opportunity_id)
                for row in session.query(InstitutionalOpportunityModel).filter(
                    InstitutionalOpportunityModel.opportunity_id.in_(
                        regeneration_ids
                    ),
                    InstitutionalOpportunityModel.state
                    == "CONTRACTS_OPTIMIZED",
                ).all()
            )
            if post_regeneration_ids:
                post_regeneration = (
                    InstitutionalDynamicManagementService(session).generate(
                        opportunity_ids=post_regeneration_ids,
                    )
                )
                post_regeneration_payload = post_regeneration.__dict__
        session.commit()

        rows = session.query(
            InstitutionalOpportunityModel.state,
        ).filter(
            InstitutionalOpportunityModel.stock_scanner_run_id == source_run_id,
        ).all()
        for (state,) in rows:
            state_counts[str(state)] = state_counts.get(str(state), 0) + 1
        integrity_row = session.execute(text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE o.state = 'READY_FOR_EXECUTION'
                      AND NOT EXISTS (
                          SELECT 1
                            FROM institutional_option_strategy_comparisons sc
                            JOIN institutional_option_contract_recommendations c
                              ON c.opportunity_id = o.opportunity_id
                             AND c.strategy_candidate_id =
                                 sc.selected_strategy_candidate_id
                             AND c.option_snapshot_id = o.option_snapshot_id
                             AND c.executable IS TRUE
                           WHERE sc.opportunity_id = o.opportunity_id
                      )
                ) AS falsely_ready_contract_lineage,
                COUNT(*) FILTER (
                    WHERE o.state = 'READY_FOR_EXECUTION'
                      AND NOT EXISTS (
                          SELECT 1
                            FROM institutional_option_execution_recommendations e
                           WHERE e.opportunity_id = o.opportunity_id
                             AND e.ready_for_trade_builder IS TRUE
                             AND e.payload_json::jsonb #>>
                               '{trade_plan_certification,execution_disposition}'
                                 = 'READY_NOW'
                      )
                ) AS falsely_ready_execution_disposition,
                COUNT(*) FILTER (
                    WHERE o.state = 'STRATEGIES_GENERATED'
                      AND COALESCE(
                          (o.payload_json::jsonb #>>
                            '{metadata,m68_2_1_3_contract_regeneration_required}')::boolean,
                          false
                      )
                ) AS pending_contract_regeneration
              FROM institutional_option_opportunities o
             WHERE o.stock_scanner_run_id = :source_run_id
        """), {"source_run_id": source_run_id}).mappings().one()
        integrity = {
            key: int(value or 0)
            for key, value in dict(integrity_row).items()
        }

    payload = {
        "version": (
            "M68.2.1.4-SELECTED-STRATEGY-CONTRACT-RECOVERY-1.0"
        ),
        "inflection": result,
        "initial_entry_governance": management_payload,
        "resumed_pending_contract_regeneration": len(
            resumed_pending_contract_regeneration_ids
        ),
        "resumed_pending_contract_regeneration_ids": (
            resumed_pending_contract_regeneration_ids
        ),
        "contract_regeneration": contract_regeneration_payload,
        "post_regeneration_entry_governance": post_regeneration_payload,
        "contract_lineage_integrity": integrity,
        "current_opportunity_state_counts": state_counts,
        "next_action": (
            "Run runtime verification, restart controlled services, and run "
            "the current M64 authoritative cycle so portfolio decisions exactly "
            "match the repaired READY_NOW set."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.get("status") not in {"READY", "DEGRADED"}:
        return 2
    if result.get("coverage_status") not in {
        "COMPLETE", "COMPLETE_WITH_ABSTENTIONS"
    }:
        return 3
    if int(management_payload.get("failed") or 0) != 0:
        return 4
    if int(
        contract_regeneration_payload.get("unexpected_failures") or 0
    ) != 0:
        return 5
    completed_regeneration = (
        int(contract_regeneration_payload.get("optimized") or 0)
        + int(
            contract_regeneration_payload.get("governed_unavailable") or 0
        )
    )
    if completed_regeneration != int(
        contract_regeneration_payload.get("requested") or 0
    ):
        return 5
    if int(post_regeneration_payload.get("failed") or 0) != 0:
        return 6
    if int(integrity.get("falsely_ready_contract_lineage") or 0) != 0:
        return 7
    if int(integrity.get("falsely_ready_execution_disposition") or 0) != 0:
        return 8
    if int(integrity.get("pending_contract_regeneration") or 0) != 0:
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
