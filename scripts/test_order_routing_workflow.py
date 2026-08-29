from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from trading_ai.broker.broker_execution_service import BrokerExecutionService
from trading_ai.broker.broker_idempotency_registry import BrokerIdempotencyRegistry
from trading_ai.broker.broker_order_service import BrokerOrderService
from trading_ai.broker.broker_profile import BrokerAuthenticationRequest
from trading_ai.broker.broker_service import BrokerService
from trading_ai.broker.fake_broker_adapter import FakeBrokerAdapter
from trading_ai.broker.fake_broker_execution_adapter import FakeBrokerExecutionAdapter
from trading_ai.broker.instrument_mapper import InstrumentMapper

from trading_ai.order_management.order_audit_ledger import OrderAuditLedger
from trading_ai.order_management.order_command_handler import OrderCommandHandler
from trading_ai.order_management.order_event_journal import OrderEventJournal
from trading_ai.order_management.order_execution_router import OrderExecutionRouter
from trading_ai.order_management.order_persistence_service import OrderPersistenceService
from trading_ai.order_management.order_profile import CanonicalOrderCommand, CanonicalOrderLeg
from trading_ai.order_management.order_repository import JsonOrderRepository
from trading_ai.order_management.order_repository_policy import OrderRepositoryPolicy
from trading_ai.order_management.order_routing_profile import OrderRouteCandidate
from trading_ai.order_management.order_service import CanonicalOrderService
from trading_ai.order_management.order_workflow_serialization import dumps
from trading_ai.order_management.order_workflow_service import OrderWorkflowService


def main() -> None:
    future = date.today() + timedelta(days=45)
    mapper = InstrumentMapper()
    option_mapping = mapper.map({
        "asset_class": "OPTION",
        "underlying_symbol": "AAPL",
        "expiration": future.isoformat(),
        "strike": 200.0,
        "option_type": "CALL",
    })
    assert option_mapping.allowed

    broker_adapter = FakeBrokerAdapter()
    broker_service = BrokerService(broker_adapter)
    assert broker_service.authenticate(
        BrokerAuthenticationRequest(
            environment="paper",
            account_id="PAPER-001",
        )
    ).allowed

    execution_adapter = FakeBrokerExecutionAdapter()

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        policy = OrderRepositoryPolicy()
        repository = JsonOrderRepository(root / "orders.json", policy)
        persistence = OrderPersistenceService(
            repository=repository,
            journal=OrderEventJournal(root / "events.jsonl", policy),
            audit_ledger=OrderAuditLedger(root / "audit.jsonl", policy),
            policy=policy,
        )
        broker_execution = BrokerExecutionService(
            broker_service=broker_service,
            execution_adapter=execution_adapter,
            order_service=BrokerOrderService(),
            idempotency_registry=BrokerIdempotencyRegistry(
                root / "broker_idempotency.json"
            ),
        )
        router = OrderExecutionRouter((
            OrderRouteCandidate(
                route_id="paper",
                broker="fake",
                environment="paper",
                account_id="PAPER-001",
                supports_equities=True,
                supports_options=True,
                supports_multi_leg_options=True,
                supports_live_trading=False,
                priority=10,
            ),
        ))
        workflow = OrderWorkflowService(
            command_handler=OrderCommandHandler(CanonicalOrderService()),
            persistence_service=persistence,
            router=router,
            broker_execution_services={"paper": broker_execution},
            repository=repository,
        )

        command = CanonicalOrderCommand(
            command_id="cmd-create-001",
            command_type="CREATE",
            aggregate_id="agg-workflow-001",
            client_order_id="client-workflow-001",
            account_id="PAPER-001",
            idempotency_key="idem-workflow-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=5.00,
            strategy_name="LONG_CALL",
            legs=(
                CanonicalOrderLeg(
                    leg_id="leg-1",
                    symbol=option_mapping.canonical_symbol,
                    broker_symbol=option_mapping.broker_symbol,
                    asset_class="OPTION",
                    side="BUY_TO_OPEN",
                    quantity=1,
                    position_effect="OPEN",
                ),
            ),
        )

        created = workflow.create(command)
        assert created.allowed
        assert created.state == "NEW"
        assert created.aggregate_version == 1

        routed = workflow.validate_and_route(
            command.aggregate_id,
            requested_route="paper",
        )
        assert routed.allowed
        assert routed.state == "ROUTED"
        assert routed.aggregate_version == 3
        assert routed.routing_decision is not None
        assert routed.routing_decision.route_id == "paper"

        submitted = workflow.submit(
            command.aggregate_id,
            route_id="paper",
            instrument_mappings={"leg-1": option_mapping},
        )
        assert submitted.allowed
        assert submitted.state == "SUBMITTED"
        assert submitted.aggregate_version == 4
        assert submitted.broker_result is not None
        assert submitted.broker_result.status == "ACCEPTED"

        aggregate = repository.require(command.aggregate_id)
        assert aggregate.state == "SUBMITTED"
        assert aggregate.broker_order_id is not None
        assert len(execution_adapter.list_orders("PAPER-001")) == 1

        replay = persistence.replay(command.aggregate_id)
        assert replay.allowed
        assert replay.event_count == 4
        assert replay.final_state == "SUBMITTED"

        valid, errors = persistence.verify_integrity()
        assert valid
        assert errors == ()

        unavailable = workflow.submit(
            command.aggregate_id,
            route_id="missing",
            instrument_mappings={"leg-1": option_mapping},
        )
        assert not unavailable.allowed
        assert "ROUTED_STATE_REQUIRED" in unavailable.rejection_reasons

        bad_router = OrderExecutionRouter((
            OrderRouteCandidate(
                route_id="paper",
                broker="fake",
                environment="paper",
                account_id="OTHER-ACCOUNT",
                supports_equities=True,
                supports_options=False,
                supports_multi_leg_options=False,
                supports_live_trading=False,
            ),
        ))
        bad_decision = bad_router.select(repository.require(command.aggregate_id))
        assert not bad_decision.allowed
        assert "ACCOUNT_MATCH" in bad_decision.rejection_reasons
        assert "OPTIONS_CAPABILITY" in bad_decision.rejection_reasons

        payload = dumps(submitted)
        assert '"state": "SUBMITTED"' in payload
        assert '"status": "ACCEPTED"' in payload

    print(
        "All broker routing, command handling, and order workflow "
        "orchestration assertions passed."
    )


if __name__ == "__main__":
    main()
