from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from trading_ai.broker.broker_execution_profile import (
    BrokerCancelRequest,
    BrokerReplaceRequest,
)
from trading_ai.broker.broker_execution_serialization import dumps
from trading_ai.broker.broker_execution_service import (
    BrokerExecutionService,
)
from trading_ai.broker.broker_idempotency_registry import (
    BrokerIdempotencyRegistry,
)
from trading_ai.broker.broker_order_profile import (
    BrokerOrderLeg,
    BrokerOrderRequest,
)
from trading_ai.broker.broker_order_service import BrokerOrderService
from trading_ai.broker.broker_profile import (
    BrokerAuthenticationRequest,
)
from trading_ai.broker.broker_service import BrokerService
from trading_ai.broker.fake_broker_adapter import FakeBrokerAdapter
from trading_ai.broker.fake_broker_execution_adapter import (
    FakeBrokerExecutionAdapter,
)
from trading_ai.broker.instrument_mapper import InstrumentMapper


def main() -> None:
    future = date.today() + timedelta(days=45)
    mapper = InstrumentMapper()

    call = mapper.map(
        {
            "asset_class": "OPTION",
            "underlying_symbol": "AAPL",
            "expiration": future.isoformat(),
            "strike": 200.0,
            "option_type": "CALL",
        }
    )
    assert call.allowed

    broker_adapter = FakeBrokerAdapter()
    broker_service = BrokerService(broker_adapter)
    readiness = broker_service.authenticate(
        BrokerAuthenticationRequest(
            environment="paper",
            account_id="PAPER-001",
        )
    )
    assert readiness.allowed

    execution_adapter = FakeBrokerExecutionAdapter()

    with tempfile.TemporaryDirectory() as temp_dir:
        registry_path = (
            Path(temp_dir)
            / "config"
            / "broker_idempotency_registry.json"
        )
        registry = BrokerIdempotencyRegistry(registry_path)
        service = BrokerExecutionService(
            broker_service=broker_service,
            execution_adapter=execution_adapter,
            order_service=BrokerOrderService(),
            idempotency_registry=registry,
        )

        order = BrokerOrderRequest(
            client_order_id="submit-001",
            account_id="PAPER-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=5.25,
            idempotency_key="idem-submit-001",
            strategy_name="LONG_CALL",
            legs=(
                BrokerOrderLeg(
                    leg_id="leg-1",
                    instrument=call,
                    side="BUY_TO_OPEN",
                    quantity=1,
                    position_effect="OPEN",
                ),
            ),
        )

        submitted = service.submit(order)
        assert submitted.allowed
        assert submitted.status == "ACCEPTED"
        assert submitted.broker_order_id is not None
        assert not submitted.replayed
        assert registry_path.exists()

        replayed = service.submit(order)
        assert replayed.allowed
        assert replayed.replayed
        assert replayed.recommendation == "RETURN_CACHED_RESULT"
        assert replayed.broker_order_id == submitted.broker_order_id
        assert len(execution_adapter.list_orders()) == 1

        mismatched = BrokerOrderRequest(
            client_order_id="submit-001",
            account_id="PAPER-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=6.00,
            idempotency_key="idem-submit-001",
            strategy_name="LONG_CALL",
            legs=order.legs,
        )
        mismatch_result = service.submit(mismatched)
        assert not mismatch_result.allowed
        assert mismatch_result.replayed
        assert (
            "IDEMPOTENCY_PAYLOAD_MATCH"
            in mismatch_result.rejection_reasons
        )

        replacement_order = BrokerOrderRequest(
            client_order_id="replace-001",
            account_id="PAPER-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=5.00,
            idempotency_key="replacement-order-key",
            strategy_name="LONG_CALL",
            legs=order.legs,
        )
        replaced = service.replace(
            BrokerReplaceRequest(
                broker_order_id=submitted.broker_order_id,
                replacement_order=replacement_order,
                client_request_id="replace-request-001",
                idempotency_key="idem-replace-001",
                reason="IMPROVE_LIMIT",
            )
        )
        assert replaced.allowed
        assert replaced.status == "ACCEPTED"
        assert replaced.order_state is not None
        assert (
            replaced.order_state.parent_broker_order_id
            == submitted.broker_order_id
        )
        assert replaced.order_state.replace_count == 1

        replace_replay = service.replace(
            BrokerReplaceRequest(
                broker_order_id=submitted.broker_order_id,
                replacement_order=replacement_order,
                client_request_id="replace-request-001",
                idempotency_key="idem-replace-001",
                reason="IMPROVE_LIMIT",
            )
        )
        assert replace_replay.allowed
        assert replace_replay.replayed
        assert replace_replay.broker_order_id == replaced.broker_order_id

        canceled = service.cancel(
            BrokerCancelRequest(
                broker_order_id=replaced.broker_order_id,
                account_id="PAPER-001",
                client_request_id="cancel-request-001",
                idempotency_key="idem-cancel-001",
                reason="USER_REQUEST",
            )
        )
        assert canceled.allowed
        assert canceled.status == "CANCELED"

        cancel_replay = service.cancel(
            BrokerCancelRequest(
                broker_order_id=replaced.broker_order_id,
                account_id="PAPER-001",
                client_request_id="cancel-request-001",
                idempotency_key="idem-cancel-001",
                reason="USER_REQUEST",
            )
        )
        assert cancel_replay.allowed
        assert cancel_replay.replayed
        assert cancel_replay.status == "CANCELED"

        second_cancel = service.cancel(
            BrokerCancelRequest(
                broker_order_id=replaced.broker_order_id,
                account_id="PAPER-001",
                client_request_id="cancel-request-002",
                idempotency_key="idem-cancel-002",
                reason="SECOND_REQUEST",
            )
        )
        assert not second_cancel.allowed
        assert "ORDER_CANCELLABLE" in second_cancel.rejection_reasons

        registry_reloaded = BrokerIdempotencyRegistry(registry_path)
        assert len(registry_reloaded.all()) == 3

        payload = dumps(replaced)
        assert '"action": "REPLACE"' in payload
        assert '"replace_count": 1' in payload

    print(
        "All broker submission, cancellation, replacement and "
        "idempotency-service assertions passed."
    )


if __name__ == "__main__":
    main()
