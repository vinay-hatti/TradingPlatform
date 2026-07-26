from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from .profile import ReplaySelector, ReplaySource


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"raw": str(value)}


class HistoricalReplayRepository:
    def __init__(self, session) -> None:
        self.session = session

    def _scanner_run(self, selector: ReplaySelector):
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if selector.scanner_run_id:
            clauses.append("scanner_run_id = :scanner_run_id")
            params["scanner_run_id"] = selector.scanner_run_id
        if selector.ingestion_run_id:
            clauses.append("ingestion_run_id = :ingestion_run_id")
            params["ingestion_run_id"] = selector.ingestion_run_id
        if selector.publication_name:
            clauses.append("publication_name = :publication_name")
            params["publication_name"] = selector.publication_name
        where = " AND ".join(clauses) or "1 = 0"
        return self.session.execute(text(f"""
            SELECT * FROM scanner_lineage_run
             WHERE {where}
             ORDER BY completed_at DESC NULLS LAST, started_at DESC
             LIMIT 1
        """), params).mappings().one_or_none()

    def _decision_run(self, selector: ReplaySelector, scanner_run_id: str | None):
        if selector.decision_run_id:
            return self.session.execute(text("""
                SELECT * FROM institutional_decision_lineage_run
                 WHERE decision_run_id = :decision_run_id LIMIT 1
            """), {"decision_run_id": selector.decision_run_id}).mappings().one_or_none()
        if scanner_run_id:
            return self.session.execute(text("""
                SELECT r.*
                  FROM institutional_decision_lineage_run r
                  JOIN institutional_decision_lineage d ON d.decision_run_id = r.decision_run_id
                 WHERE d.scanner_run_id = :scanner_run_id
                 ORDER BY r.completed_at DESC NULLS LAST, r.started_at DESC
                 LIMIT 1
            """), {"scanner_run_id": scanner_run_id}).mappings().one_or_none()
        if selector.ingestion_run_id:
            return self.session.execute(text("""
                SELECT * FROM institutional_decision_lineage_run
                 WHERE ingestion_run_id = :ingestion_run_id
                 ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1
            """), {"ingestion_run_id": selector.ingestion_run_id}).mappings().one_or_none()
        return None

    def load(self, selector: ReplaySelector) -> ReplaySource:
        selector.validate()
        scanner = self._scanner_run(selector)
        decision = self._decision_run(selector, scanner["scanner_run_id"] if scanner else None)
        if scanner is None and decision is None:
            raise LookupError("No persisted scanner or decision lineage matched the replay selector")

        scanner_run_id = str(scanner["scanner_run_id"]) if scanner else None
        decision_run_id = str(decision["decision_run_id"]) if decision else None
        candidates = ()
        if scanner_run_id:
            rows = self.session.execute(text("""
                SELECT payload_json FROM scanner_candidate_lineage
                 WHERE scanner_run_id = :scanner_run_id ORDER BY rank, candidate_id
            """), {"scanner_run_id": scanner_run_id}).mappings().all()
            candidates = tuple(_json(row["payload_json"]) for row in rows)
        decisions = ()
        if decision_run_id:
            rows = self.session.execute(text("""
                SELECT payload_json FROM institutional_decision_lineage
                 WHERE decision_run_id = :decision_run_id ORDER BY decision_id
            """), {"decision_run_id": decision_run_id}).mappings().all()
            decisions = tuple(_json(row["payload_json"]) for row in rows)

        base = scanner or decision
        return ReplaySource(
            publication_name=base.get("publication_name"),
            ingestion_run_id=base.get("ingestion_run_id"),
            publication_status=str(base.get("publication_status") or "UNKNOWN"),
            market_as_of_date=str(scanner.get("market_as_of_date")) if scanner and scanner.get("market_as_of_date") else None,
            market_intelligence_snapshot_timestamp=str(base.get("market_intelligence_snapshot_timestamp")) if base.get("market_intelligence_snapshot_timestamp") else None,
            option_snapshot_timestamp=str(base.get("option_snapshot_timestamp")) if base.get("option_snapshot_timestamp") else None,
            option_snapshot_id=base.get("option_snapshot_id"),
            market_state_hash=base.get("market_state_hash"),
            scanner_run_id=scanner_run_id,
            scanner_version=scanner.get("scanner_version") if scanner else None,
            decision_run_id=decision_run_id,
            decision_engine_version=decision.get("decision_engine_version") if decision else None,
            policy_version=decision.get("policy_version") if decision else None,
            scanner_candidates=candidates,
            decisions=decisions,
        )
