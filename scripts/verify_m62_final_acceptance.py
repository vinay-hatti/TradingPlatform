from __future__ import annotations

from sqlalchemy import func

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.decision import InstitutionalDecisionService
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel


def target_order_valid(payload: dict) -> bool:
    thesis = dict(payload.get("thesis") or {})
    targets = [float(x) for x in thesis.get("targets") or []]
    direction = str(thesis.get("direction") or "").upper()
    expected = sorted(targets, reverse=direction == "BEARISH")
    return targets == expected


def main() -> None:
    with SessionLocal() as session:
        result = InstitutionalDecisionService(session).build()
        session.commit()
        rows = session.query(InstitutionalDecisionSnapshotModel).all()
        missing_probability = sum(row.calibrated_probability is None for row in rows)
        missing_selection = sum(
            not row.strategy_candidate_id or not row.contract_recommendation_id for row in rows
        )
        missing_hash = sum(not row.state_hash for row in rows)
        target_order_violations = sum(not target_order_valid(dict(row.payload_json or {})) for row in rows)
        print(f"Decision rebuild: requested={result.requested}, created={result.created}, refreshed={result.refreshed}, failed={result.failed}")
        for error in result.errors[:20]:
            print(f"Decision rebuild error: {error}")
        print(f"Decision snapshots: {len(rows)}")
        print(f"Missing calibrated probability: {missing_probability}")
        print(f"Missing selected strategy/contract: {missing_selection}")
        print(f"Missing state hash: {missing_hash}")
        print(f"Target-order violations: {target_order_violations}")
        if result.failed or missing_probability or missing_selection or missing_hash or target_order_violations:
            raise SystemExit("Milestone 62 final operational acceptance FAILED")
        print("Milestone 62 final operational acceptance PASSED")


if __name__ == "__main__":
    main()
