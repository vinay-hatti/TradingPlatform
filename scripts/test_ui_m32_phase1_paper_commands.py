from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.api.paper_commands import service as service_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.models.paper_commands import (
    GovernedActor,
    PaperOrderSide,
    PaperOrderSubmitRequest,
    PaperOrderType,
)
from trading_ai.ui.services.paper_command_service import (
    JsonPaperCommandRepository,
    PaperCommandService,
)


def actor():
    return GovernedActor(
        user_id="phase1-test-user",
        session_id="phase1-test-session",
        roles=["TRADER"],
        permissions=[
            "paper_orders.view",
            "paper_orders.submit",
            "paper_orders.cancel",
            "paper_orders.replace",
        ],
    )


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        command_service = PaperCommandService(
            repository=JsonPaperCommandRepository(
                state_path=root / "state.json",
                audit_path=root / "audit.jsonl",
            )
        )

        request = PaperOrderSubmitRequest(
            environment="PAPER",
            symbol="aapl",
            instrument_type="EQUITY",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.LIMIT,
            quantity=2,
            limit_price=200.0,
            reason="Validate governed paper order workflow",
            confirmation_token="CONFIRM-PAPER-phase1-test",
            idempotency_key="submit-phase1-test",
            actor=actor(),
        )
        decision = command_service.submit(request)
        assert decision.allowed
        assert decision.status == "ACCEPTED"
        assert decision.order is not None
        assert decision.order.symbol == "AAPL"

        replay = command_service.submit(request)
        assert replay.idempotent_replay
        assert replay.order.order_id == decision.order.order_id

        state = command_service.state()
        assert state.summary.live_trading_enabled is False
        assert state.summary.total_orders == 1
        assert state.summary.open_orders == 1

        app = create_app()
        app.dependency_overrides[service_dependency] = lambda: command_service
        client = TestClient(app)

        response = client.get("/api/v1/paper-commands")
        assert response.status_code == 200
        assert response.json()["summary"]["mode"] == "GOVERNED_PAPER_ONLY"

        rejected = client.post(
            "/api/v1/paper-commands/orders",
            json={
                "environment": "PAPER",
                "symbol": "MSFT",
                "instrument_type": "EQUITY",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 5000,
                "limit_price": 500.0,
                "reason": "This request must be rejected by limits",
                "confirmation_token": "CONFIRM-PAPER-reject",
                "idempotency_key": "submit-phase1-rejected",
                "actor": actor().model_dump(),
            },
        )
        assert rejected.status_code == 403

        cancel = client.post(
            f"/api/v1/paper-commands/orders/"
            f"{decision.order.order_id}/cancel",
            json={
                "environment": "PAPER",
                "reason": "Cancel phase one regression order",
                "confirmation_token": "CONFIRM-PAPER-cancel",
                "idempotency_key": "cancel-phase1-test",
                "actor": actor().model_dump(),
            },
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "CANCELLED"

        assert (root / "audit.jsonl").exists()
        assert len((root / "audit.jsonl").read_text().splitlines()) >= 3

    print(
        "All Milestone 32 Phase 1 Governed Interactive Workstation "
        "Commands and Paper-Trading Controls assertions passed."
    )


if __name__ == "__main__":
    main()
