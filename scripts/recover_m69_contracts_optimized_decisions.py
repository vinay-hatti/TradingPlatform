from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.decision import InstitutionalDecisionService
from trading_ai.institutional_options.domain import OpportunityState
from trading_ai.institutional_options.models import InstitutionalOpportunityModel


def _count_states(session, ids: tuple[str, ...]) -> dict[str, int]:
    if not ids:
        return {}
    rows = (
        session.query(InstitutionalOpportunityModel.state)
        .filter(InstitutionalOpportunityModel.opportunity_id.in_(ids))
        .all()
    )
    result: dict[str, int] = {}
    for (state,) in rows:
        result[str(state)] = result.get(str(state), 0) + 1
    return dict(sorted(result.items()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Advance CONTRACTS_OPTIMIZED opportunities through authoritative "
            "strategy valuation, governed rejection, management, and decisions."
        )
    )
    parser.add_argument("--stock-scanner-run-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as session:
        query = session.query(InstitutionalOpportunityModel.opportunity_id).filter(
            InstitutionalOpportunityModel.state
            == OpportunityState.CONTRACTS_OPTIMIZED.value
        )
        if args.stock_scanner_run_id:
            query = query.filter(
                InstitutionalOpportunityModel.stock_scanner_run_id
                == args.stock_scanner_run_id
            )
        query = query.order_by(
            InstitutionalOpportunityModel.overall_score.desc(),
            InstitutionalOpportunityModel.symbol,
        )
        if args.limit is not None:
            query = query.limit(args.limit)
        ids = tuple(row[0] for row in query.all())

        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "DRY_RUN",
                        "contracts_optimized": len(ids),
                        "opportunity_ids": ids[:20],
                    },
                    indent=2,
                )
            )
            return

        result = InstitutionalDecisionService(session).build(
            opportunity_ids=ids, limit=None
        )
        session.commit()
        final_states = _count_states(session, ids)
        remaining = final_states.get(OpportunityState.CONTRACTS_OPTIMIZED.value, 0)
        rejected = final_states.get(OpportunityState.REJECTED.value, 0)
        ready = final_states.get(OpportunityState.READY_FOR_EXECUTION.value, 0)

        print(
            json.dumps(
                {
                    "status": (
                        "READY"
                        if result.failed == 0 and remaining == 0
                        else "DEGRADED"
                    ),
                    "input_contracts_optimized": len(ids),
                    "decisions_requested": result.requested,
                    "decisions_created": result.created,
                    "decisions_refreshed": result.refreshed,
                    "decision_failures": result.failed,
                    "ready_for_execution": ready,
                    "governed_rejected": rejected,
                    "remaining_contracts_optimized": remaining,
                    "final_states": final_states,
                    "errors": list(result.errors[:100]),
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
