from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from trading_ai.broker.broker_execution_profile import BrokerCancelRequest
from trading_ai.broker.broker_execution_service import BrokerExecutionService
from trading_ai.broker.broker_idempotency_registry import (
    BrokerIdempotencyRegistry,
)
from trading_ai.broker.broker_order_profile import (
    BrokerOrderLeg,
    BrokerOrderRequest,
)
from trading_ai.broker.broker_order_service import BrokerOrderService
from trading_ai.broker.broker_profile import BrokerAuthenticationRequest
from trading_ai.broker.broker_service import BrokerService
from trading_ai.broker.broker_status_profile import BrokerPositionProfile
from trading_ai.broker.broker_status_serialization import dumps
from trading_ai.broker.broker_status_service import (
    BrokerStatusReconciliationService,
)
from trading_ai.broker.fake_broker_adapter import FakeBrokerAdapter
from trading_ai.broker.fake_broker_event_source import FakeBrokerEventSource
from trading_ai.broker.fake_broker_execution_adapter import (
    FakeBrokerExecutionAdapter,
)
from trading_ai.broker.instrument_mapper import InstrumentMapper


def main() -> None:
    future = date.today() + timedelta(days=45)
    mapper = InstrumentMapper()
    option = mapper.map(
        {
            "asset_class": "OPTION",
            "underlying_symbol": "AAPL",
            "expiration": future.isoformat(),
            "strike": 200.0,
            "option_type": "CALL",
        }
    )
    assert option.allowed
    symbol = option.canonical_symbol

    broker_adapter = FakeBrokerAdapter()
    broker_service = BrokerService(broker_adapter)
    assert broker_service.authenticate(
        BrokerAuthenticationRequest(
            environment="paper",
            account_id="PAPER-001",
        )
    ).allowed

    execution_adapter = FakeBrokerExecutionAdapter()

    with tempfile.TemporaryDirectory() as temp_dir:
        registry = BrokerIdempotencyRegistry(
            Path(temp_dir) / "config" / "idempotency.json"
        )
        execution_service = BrokerExecutionService(
            broker_service=broker_service,
            execution_adapter=execution_adapter,
            order_service=BrokerOrderService(),
            idempotency_registry=registry,
        )

        order = BrokerOrderRequest(
            client_order_id="status-order-001",
            account_id="PAPER-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=5.00,
            idempotency_key="status-idem-001",
            strategy_name="LONG_CALL",
            legs=(
                BrokerOrderLeg(
                    leg_id="leg-1",
                    instrument=option,
                    side="BUY_TO_OPEN",
                    quantity=2,
                    position_effect="OPEN",
                ),
            ),
        )
        submitted = execution_service.submit(order)
        assert submitted.allowed
        state = submitted.order_state
        assert state is not None

        status_service = BrokerStatusReconciliationService(
            execution_adapter
        )
        source = FakeBrokerEventSource()

        first_fill = source.fill(
            state,
            leg_id="leg-1",
            symbol=symbol,
            side="BUY_TO_OPEN",
            quantity=1,
            price=4.90,
            commission=0.65,
            fees=0.05,
        )
        second_fill = source.fill(
            state,
            leg_id="leg-1",
            symbol=symbol,
            side="BUY_TO_OPEN",
            quantity=1,
            price=5.10,
            commission=0.65,
            fees=0.05,
        )

        assert status_service.ingest_fill(first_fill) == ()
        assert status_service.ingest_fill(second_fill) == ()
        assert (
            status_service.ingest_fill(second_fill)
            == ("DUPLICATE_EXECUTION_ID",)
        )

        filled_status = source.status(
            state,
            "FILLED",
            filled_quantity=2,
            remaining_quantity=0,
            average_fill_price=5.00,
        )
        assert status_service.ingest_status(filled_status) == ()

        bad_regression = source.status(
            state,
            "PARTIALLY_FILLED",
            filled_quantity=-1,
            remaining_quantity=3,
        )
        reasons = status_service.ingest_status(bad_regression)
        assert "NEGATIVE_FILLED_QUANTITY" in reasons
        assert "FILLED_QUANTITY_REGRESSION" in reasons

        summaries = status_service.order_summaries("PAPER-001")
        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.status == "FILLED"
        assert summary.filled_quantity == 2
        assert summary.remaining_quantity == 0
        assert summary.average_fill_price == 5.0
        assert summary.commission == 1.30
        assert round(summary.fees, 2) == 0.10
        assert summary.fill_count == 2

        broker_positions = status_service.broker_positions(
            account_id="PAPER-001",
            asset_class_by_symbol={symbol: "OPTION"},
            multiplier_by_symbol={symbol: 100},
        )
        assert len(broker_positions) == 1
        broker_position = broker_positions[0]
        assert broker_position.quantity == 2
        assert broker_position.average_cost == 5.0
        assert broker_position.multiplier == 100

        platform_position = BrokerPositionProfile(
            broker="platform",
            account_id="PAPER-001",
            symbol=symbol,
            asset_class="OPTION",
            quantity=2,
            average_cost=5.0,
            multiplier=100,
        )
        reconciliation = status_service.reconcile(
            account_id="PAPER-001",
            platform_positions=(platform_position,),
            asset_class_by_symbol={symbol: "OPTION"},
            multiplier_by_symbol={symbol: 100},
        )
        assert reconciliation.allowed
        assert reconciliation.matched_position_count == 1
        assert reconciliation.rejected_position_count == 0
        assert reconciliation.fill_count == 2

        mismatched_platform = BrokerPositionProfile(
            broker="platform",
            account_id="PAPER-001",
            symbol=symbol,
            asset_class="OPTION",
            quantity=1,
            average_cost=6.0,
            multiplier=100,
        )
        mismatch = status_service.reconcile(
            account_id="PAPER-001",
            platform_positions=(mismatched_platform,),
            asset_class_by_symbol={symbol: "OPTION"},
            multiplier_by_symbol={symbol: 100},
        )
        assert not mismatch.allowed
        assert mismatch.rejected_position_count == 1
        reasons = mismatch.position_profiles[0].rejection_reasons
        assert "QUANTITY_MATCH" in reasons
        assert "AVERAGE_COST_MATCH" in reasons

        payload = dumps(reconciliation)
        assert '"matched_position_count": 1' in payload
        assert '"status": "FILLED"' in payload

    print(
        "All broker status, fill, position synchronization and "
        "reconciliation assertions passed."
    )


if __name__ == "__main__":
    main()
