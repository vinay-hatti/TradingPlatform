from __future__ import annotations

from datetime import datetime, timezone
import json
import tempfile
from pathlib import Path

from trading_ai.replay import HistoricalReplayService, ReplayPolicy, ReplaySelector, ReplaySource, content_hash


SOURCE = ReplaySource(
    publication_name="current_market_state",
    ingestion_run_id="readiness-20260725T235216499119Z",
    publication_status="DEGRADED",
    market_as_of_date="2026-07-23",
    market_intelligence_snapshot_timestamp="2026-07-25T23:49:40Z",
    option_snapshot_timestamp="2026-07-25T17:45:07Z",
    option_snapshot_id="polygon-20260725T174507270627Z-ed7dec67",
    market_state_hash="abc123",
    scanner_run_id="scanner-test",
    scanner_version="m47.phase6.v1",
    decision_run_id="decision-test",
    decision_engine_version="m47.phase6.v1",
    policy_version="published-state.v1",
    scanner_candidates=(
        {"candidate_id": "old-1", "scanner_run_id": "old", "symbol": "MSFT", "signal": "PUT", "strategy": "LONG_PUT", "score": 69.95},
        {"candidate_id": "old-2", "scanner_run_id": "old", "symbol": "AAPL", "signal": "CALL", "strategy": "LONG_CALL", "score": 68.55},
    ),
    decisions=(
        {"decision_id": "d-old", "decision_run_id": "old", "symbol": "AAPL", "strategy": "LONG_CALL", "action": "ACCEPT", "confidence": 81.85},
    ),
)


class Repository:
    def __init__(self, session):
        self.session = session

    def load(self, selector):
        selector.validate()
        return SOURCE


class Session:
    def __enter__(self): return self
    def __exit__(self, *args): return False


def factory(): return Session()


def main() -> None:
    assert content_hash({"candidate_id": "x", "symbol": "AAPL"}) == content_hash({"candidate_id": "y", "symbol": "AAPL"})

    policy = ReplayPolicy(persist_replay=False)
    service = HistoricalReplayService(factory, repository_factory=Repository, policy=policy)
    snapshot = service.run(ReplaySelector(scanner_run_id="scanner-test"), mode="snapshot")
    assert snapshot.status == "READY"
    assert snapshot.matched
    assert len(snapshot.replay_candidates) == 2
    assert snapshot.metadata["mismatch_count"] == 0

    def scanner_executor(source):
        return [dict(item, candidate_id="new", scanner_run_id="new") for item in source.scanner_candidates]

    execute = HistoricalReplayService(
        factory,
        repository_factory=Repository,
        scanner_executor=scanner_executor,
        decision_executor=lambda source, candidates: [dict(item, decision_id="new", decision_run_id="new") for item in source.decisions],
        policy=policy,
    ).run(ReplaySelector(ingestion_run_id="readiness-20260725T235216499119Z"), mode="execute")
    assert execute.status == "READY"
    assert execute.matched

    def changed_executor(source):
        rows = [dict(item) for item in source.scanner_candidates]
        rows[0]["score"] = 1.0
        return rows

    changed = HistoricalReplayService(
        factory, repository_factory=Repository, scanner_executor=changed_executor, policy=policy
    ).run(ReplaySelector(publication_name="current_market_state"), mode="execute")
    assert changed.status == "FAILED"
    assert changed.metadata["mismatch_count"] >= 1

    with tempfile.TemporaryDirectory() as directory:
        paths = service.export(snapshot, directory)
        payload = json.loads(Path(paths["json"]).read_text())
        manifest = json.loads(Path(paths["manifest"]).read_text())
        assert payload["replay_run_id"] == snapshot.replay_run_id
        assert manifest["report_type"] == "historical_replay"
        assert manifest["metadata"]["mismatch_count"] == 0
        assert manifest["artifacts"][0]["sha256"]

    print("Milestone 47 Phase 7 historical-replay assertions passed.")


if __name__ == "__main__":
    main()
