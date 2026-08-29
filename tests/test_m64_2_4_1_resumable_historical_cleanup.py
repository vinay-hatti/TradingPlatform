from __future__ import annotations

from types import SimpleNamespace

from trading_ai.portfolio_risk_allocation.decision_intelligence import (
    InstitutionalDecisionIntelligenceService,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    M64HistoryCleanupIncompleteError,
)


def test_cleanup_incomplete_error_is_retryable_and_reports_remaining():
    error = M64HistoryCleanupIncompleteError(
        "PAPER-PRIMARY",
        {
            "status": "INCOMPLETE_RETRYABLE",
            "retired": 55_000,
            "remaining": 2_500,
        },
    )
    payload = error.as_dict()
    assert payload["status"] == "DEFERRED_HISTORY_CLEANUP"
    assert payload["retryable"] is True
    assert payload["historical_cleanup"]["remaining"] == 2_500


def test_non_authoritative_cleanup_commits_each_server_side_batch():
    class FakeResult:
        def __init__(self, row=None):
            self.row = row

        def one(self):
            return self.row

    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __init__(self, mode, batch_rows=0):
            self.mode = mode
            self.batch_rows = batch_rows
            self.statements: list[str] = []
            self.commits = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def scalar(self, statement, parameters=None):
            self.statements.append(str(statement))
            if self.mode == "metadata":
                return SimpleNamespace(
                    risk_snapshot_id="M64-RISK-AUTHORITATIVE",
                    payload_json={"stock_scanner_run_id": "stock-run-authoritative"},
                )
            if self.mode == "count":
                return 0
            raise AssertionError(f"unexpected scalar in {self.mode}")

        def execute(self, statement, parameters=None):
            rendered = str(statement)
            self.statements.append(rendered)
            if rendered.lstrip().startswith("SET LOCAL"):
                return FakeResult()
            assert self.mode == "batch"
            return FakeResult(SimpleNamespace(
                updated_count=self.batch_rows,
                first_decision_id=(
                    f"M64-DI-FIRST-{self.batch_rows}"
                    if self.batch_rows
                    else None
                ),
                last_decision_id=(
                    f"M64-DI-LAST-{self.batch_rows}"
                    if self.batch_rows
                    else None
                ),
            ))

        def commit(self):
            self.commits += 1

    sessions = [
        FakeSession("metadata"),
        FakeSession("batch", 1_000),
        FakeSession("batch", 12),
        FakeSession("batch", 0),
        FakeSession("count"),
    ]

    def factory():
        return sessions.pop(0)

    events: list[tuple[str, dict]] = []
    service = InstitutionalDecisionIntelligenceService(factory)
    result = service.compact_non_authoritative_history(
        "PAPER-PRIMARY",
        progress=lambda stage, details: events.append((stage, details)),
    )
    assert result["status"] == "COMPLETE"
    assert result["retired"] == 1_012
    assert result["remaining"] == 0
    assert result["batch_count"] == 2
    committed = [
        details
        for stage, details in events
        if stage == "historical_decision_cleanup_batch_committed"
    ]
    assert [item["batch_rows"] for item in committed] == [1_000, 12]
    assert all(
        item["execution_mode"] == "POSTGRESQL_RESUMABLE_COMMITTED_JSONB"
        for item in committed
    )


def test_release_sources_include_resumable_cleanup_contract():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    decisions = (
        root / "src/trading_ai/portfolio_risk_allocation/decision_intelligence.py"
    ).read_text()
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()
    operator = (
        root / "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py"
    ).read_text()
    assert "NON_AUTHORITATIVE_HISTORY_COMPACTION" in decisions
    assert "POSTGRESQL_RESUMABLE_COMMITTED_JSONB" in decisions
    assert "session.commit()" in decisions
    assert "M64HistoryCleanupIncompleteError" in orchestration
    assert "DEFERRED_HISTORY_CLEANUP" in orchestration
    assert "M64HistoryCleanupIncompleteError" in operator
