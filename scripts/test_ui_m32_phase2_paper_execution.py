from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.api.paper_execution import service as service_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.broker.paper_broker_adapter import LocalPaperBrokerAdapter
from trading_ai.ui.models.paper_commands import (
    PaperOrderRecord,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
)
from trading_ai.ui.services.paper_execution_service import PaperExecutionService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        now = datetime.now(timezone.utc)
        command_state = root / "paper_trading_state.json"
        command_state.write_text(
            """
{
  "orders": [
    {
      "order_id": "paper-phase2-1",
      "environment": "PAPER",
      "symbol": "AAPL",
      "instrument_type": "EQUITY",
      "side": "BUY",
      "order_type": "LIMIT",
      "quantity": 4,
      "limit_price": 200.0,
      "estimated_price": null,
      "option_expiry": null,
      "option_strike": null,
      "option_type": null,
      "status": "ACCEPTED",
      "reason": "Phase 2 regression",
      "actor_user_id": "tester",
      "actor_session_id": "session",
      "idempotency_key": "phase2-idempotency",
      "created_at": "%s",
      "updated_at": "%s",
      "replaced_by_order_id": null,
      "rejection_reasons": []
    }
  ]
}
""" % (now.isoformat(), now.isoformat()),
            encoding="utf-8",
        )

        service = PaperExecutionService(
            command_state_path=command_state,
            broker=LocalPaperBrokerAdapter(
                state_path=root / "paper_broker_state.json"
            ),
        )

        submitted = service.synchronize_orders({"AAPL": 199.5})
        assert submitted == 1
        assert len(service.broker.list_orders()) == 1

        partial = service.simulate_open_order_fills(
            {"AAPL": 199.5},
            max_fill_quantity=2,
        )
        assert partial == 2

        state = service.state()
        assert state.summary.total_orders == 1
        assert state.summary.total_fills == 1
        assert state.orders[0].status.value == "PARTIAL"
        assert state.positions[0].quantity == 2

        completed = service.simulate_open_order_fills(
            {"AAPL": 199.0},
            max_fill_quantity=10,
        )
        assert completed == 2

        state = service.state()
        assert state.orders[0].status.value == "FILLED"
        assert state.positions[0].quantity == 4
        assert state.reconciliation.issue_count == 0

        app = create_app()
        app.dependency_overrides[service_dependency] = lambda: service
        client = TestClient(app)

        response = client.get("/api/v1/paper-execution")
        assert response.status_code == 200
        assert response.json()["summary"]["live_trading_enabled"] is False

        reconcile = client.get(
            "/api/v1/paper-execution/reconciliation"
        )
        assert reconcile.status_code == 200
        assert reconcile.json()["issue_count"] == 0

    print(
        "All Milestone 32 Phase 2 Broker-Backed Paper Execution, "
        "Fill Simulation, Position Synchronization, and Reconciliation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
