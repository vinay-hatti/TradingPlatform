from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from trading_ai.portfolio_risk_allocation.decision_intelligence import (
    InstitutionalDecisionIntelligenceService,
)
from trading_ai.portfolio_risk_allocation.orchestration import M64CycleBusyError


ROOT = Path(__file__).resolve().parents[1]


def test_busy_error_is_structured_and_retryable():
    error = M64CycleBusyError(
        "PAPER-PRIMARY",
        2.5,
        {"pid": 1234, "state": "idle in transaction"},
    )
    payload = error.as_dict()
    assert payload["status"] == "DEFERRED_BUSY"
    assert payload["retryable"] is True
    assert payload["lock_owner"]["pid"] == 1234
    assert payload["lock_timeout_seconds"] == 2.5


def test_postgresql_retirement_uses_bounded_server_side_batches():
    class FakeResult:
        def __init__(self, row):
            self.row = row

        def one(self):
            return self.row

    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __init__(self):
            self.counts = iter((500, 2, 0))
            self.statements: list[str] = []

        def execute(self, statement, parameters=None):
            rendered = str(statement)
            self.statements.append(rendered)
            if rendered.lstrip().startswith("SET LOCAL"):
                return FakeResult(None)
            if "SELECT COUNT(*)" in rendered:
                return FakeResult(None)
            count = next(self.counts)
            return FakeResult(SimpleNamespace(
                updated_count=count,
                first_decision_id="M64-DI-FIRST" if count else None,
                last_decision_id="M64-DI-LAST" if count else None,
            ))

        def scalar(self, statement, parameters=None):
            self.statements.append(str(statement))
            return 0

    session = FakeSession()
    service = InstitutionalDecisionIntelligenceService(lambda: None)
    events: list[tuple[str, dict]] = []
    retired = service._retire_stale_decisions(
        session,
        portfolio_id="PAPER-PRIMARY",
        current_risk_snapshot_id="M64-RISK-CURRENT",
        current_stock_run_id="stock-run-current",
        progress=lambda stage, details: events.append((stage, details)),
    )
    assert retired == 502
    batches = [details for stage, details in events if stage == "stale_decision_retirement_batch"]
    assert [item["batch_rows"] for item in batches] == [500, 2]
    assert all(item["execution_mode"] == "POSTGRESQL_SERVER_SIDE_JSONB" for item in batches)
    sql = "\n".join(session.statements)
    assert "FOR UPDATE" in sql
    assert "jsonb_build_object" in sql
    assert "sha256(convert_to" in sql


def test_broker_sync_never_invokes_m64_synchronously():
    source = (ROOT / "src/trading_ai/broker_portfolio_sync/service.py").read_text()
    assert "DEFERRED_TO_DEDICATED_SCHEDULER" in source
    assert "Milestone64ContinuousPortfolioIntelligenceService" not in source
    assert '"blocking": False' in source


def test_scheduled_and_operator_entry_points_have_bounded_lock_behavior():
    scheduler = (ROOT / "scripts/run_m64_portfolio_intelligence.py").read_text()
    operator = (
        ROOT / "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py"
    ).read_text()
    assert "cycle_deferred_busy" in scheduler
    assert 'default=0.0' in scheduler
    assert "return 75" in operator
    assert 'default=30.0' in operator
