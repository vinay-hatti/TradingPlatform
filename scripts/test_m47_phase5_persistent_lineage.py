from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_ai.lineage import DecisionRunLineage, LineagePersistenceService, ScannerRunLineage


class FakeResult:
    overall_readiness = "READY"
    metadata = {}
    decisions = []


@dataclass
class Candidate:
    symbol: str = "AAPL"
    signal: str = "CALL"
    strategy: str = "LONG_CALL"
    ai_score: float = 81.5
    scanner_run_id: str = ""
    candidate_id: str = ""
    market_state_hash: str = ""
    scanner_version: str = ""


class FakeSession:
    def __init__(self):
        self.statements = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), dict(parameters or {})))

    def commit(self):
        self.committed = True


def main():
    sessions = []

    def factory():
        session = FakeSession()
        sessions.append(session)
        return session

    service = LineagePersistenceService(factory)
    candidate = Candidate()
    scanner = ScannerRunLineage(
        scanner_run_id="scanner-test",
        publication_name="current_market_state",
        ingestion_run_id="ingestion-test",
        publication_status="DEGRADED",
        published_at="2026-07-25T21:00:00+00:00",
        market_as_of_date="2026-07-23",
        market_intelligence_snapshot_timestamp="2026-07-25T20:00:00+00:00",
        option_snapshot_timestamp="2026-07-25T17:00:00+00:00",
        option_snapshot_id="polygon-test",
        option_snapshot_completeness_pct=99.5,
        published_state_degraded=True,
        scanner_version="m47.phase5.v1",
        started_at=datetime.now(timezone.utc),
    )
    summary = service.persist_scanner_run(scanner, [candidate])
    assert summary.run_rows == 1 and summary.item_rows == 1
    assert candidate.scanner_run_id == "scanner-test"
    assert candidate.candidate_id.startswith("cand-")
    assert len(candidate.market_state_hash) == 64
    assert sessions[-1].committed
    assert any("INSERT INTO scanner_lineage_run" in sql for sql, _ in sessions[-1].statements)
    assert any("INSERT INTO scanner_candidate_lineage" in sql for sql, _ in sessions[-1].statements)

    decision = type("Decision", (), {"symbol": "AAPL", "strategy": "LONG_CALL", "confidence": 82.0, "accepted": True})()
    result = type("DecisionResult", (), {"decisions": [decision], "overall_readiness": "READY"})()
    profile = DecisionRunLineage(
        decision_run_id="decision-test",
        publication_name="current_market_state",
        ingestion_run_id="ingestion-test",
        publication_status="DEGRADED",
        market_intelligence_snapshot_timestamp="2026-07-25T20:00:00+00:00",
        option_snapshot_timestamp="2026-07-25T17:00:00+00:00",
        option_snapshot_id="polygon-test",
        published_state_degraded=True,
        decision_engine_version="m47.phase5.v1",
        policy_version="published-state.v1",
        started_at=datetime.now(timezone.utc),
    )
    summary = service.persist_decision_run(profile, result)
    assert summary.item_rows == 1
    assert decision.decision_run_id == "decision-test"
    assert decision.decision_id.startswith("decision-")
    assert any("INSERT INTO institutional_decision_lineage_run" in sql for sql, _ in sessions[-1].statements)
    assert any("INSERT INTO institutional_decision_lineage" in sql for sql, _ in sessions[-1].statements)

    migration = Path("migrations/versions/m47_001_persistent_lineage.py").read_text()
    for table in (
        "scanner_lineage_run", "scanner_candidate_lineage",
        "institutional_decision_lineage_run", "institutional_decision_lineage",
    ):
        assert table in migration
    assert 'revision = "m47_001"' in migration
    assert 'down_revision = "m46_003"' in migration
    print("Milestone 47 Phase 5 persistent-lineage assertions passed.")


if __name__ == "__main__":
    main()
