from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from trading_ai.portfolio_risk_allocation.decision_intelligence import (
    InstitutionalDecisionIntelligenceService,
)


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def one(self):
        return self.row


class FakeQueryCanceled(Exception):
    pgcode = "57014"


class FakeSession:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def __init__(self, mode: str, *, batch_rows: int = 0, remaining: int = 0):
        self.mode = mode
        self.batch_rows = batch_rows
        self.remaining = remaining
        self.statements: list[str] = []
        self.commits = 0
        self.rollbacks = 0

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
            return self.remaining
        raise AssertionError(f"unexpected scalar in {self.mode}")

    def execute(self, statement, parameters=None):
        rendered = str(statement)
        self.statements.append(rendered)
        if rendered.lstrip().startswith("SET LOCAL"):
            return FakeResult()
        if self.mode == "timeout":
            raise OperationalError(
                rendered,
                parameters,
                FakeQueryCanceled("canceling statement due to statement timeout"),
            )
        assert self.mode == "batch"
        return FakeResult(SimpleNamespace(
            updated_count=self.batch_rows,
            first_decision_id="M64-DI-FIRST",
            last_decision_id="M64-DI-LAST",
        ))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_query_canceled_checkpoint_becomes_retryable_after_prior_commit():
    metadata = FakeSession("metadata")
    committed = FakeSession("batch", batch_rows=1_000)
    canceled = FakeSession("timeout")
    count = FakeSession("count", remaining=2_500)
    sessions = [metadata, committed, canceled, count]

    def factory():
        return sessions.pop(0)

    events: list[tuple[str, dict]] = []
    service = InstitutionalDecisionIntelligenceService(factory)
    result = service.compact_non_authoritative_history(
        "PAPER-PRIMARY",
        progress=lambda stage, details: events.append((stage, details)),
    )

    assert result["status"] == "INCOMPLETE_RETRYABLE"
    assert result["complete"] is False
    assert result["retired"] == 1_000
    assert result["remaining"] == 2_500
    assert result["batch_count"] == 1
    assert result["deferred_reason"] == "POSTGRESQL_QUERY_CANCELED"
    assert committed.commits == 1
    assert canceled.commits == 0
    assert canceled.rollbacks == 1
    assert any(
        stage == "historical_decision_cleanup_batch_deferred"
        and details["sqlstate"] == "57014"
        for stage, details in events
    )


def test_cleanup_never_uses_sub_ten_second_statement_timeout():
    metadata = FakeSession("metadata")
    empty_batch = FakeSession("batch", batch_rows=0)
    count = FakeSession("count", remaining=0)
    sessions = [metadata, empty_batch, count]

    def factory():
        return sessions.pop(0)

    service = InstitutionalDecisionIntelligenceService(factory)
    result = service.compact_non_authoritative_history("PAPER-PRIMARY")

    timeout_statements = [
        statement
        for statement in empty_batch.statements
        if "statement_timeout" in statement
    ]
    assert result["status"] == "COMPLETE"
    assert timeout_statements
    timeout_ms = int(timeout_statements[0].split("'")[1].removesuffix("ms"))
    assert timeout_ms >= 10_000
