from __future__ import annotations

import tempfile
from datetime import date, timedelta
from dataclasses import replace
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
from trading_ai.order_management.order_event_journal import OrderEventJournal
from trading_ai.order_management.order_group_engine import OrderGroupEngine
from trading_ai.order_management.order_group_repository import JsonOrderGroupRepository
from trading_ai.order_management.order_group_workflow_service import OrderGroupWorkflowService
from trading_ai.order_management.order_linkage_serialization import dumps
from trading_ai.order_management.order_persistence_service import OrderPersistenceService
from trading_ai.order_management.order_profile import CanonicalOrderCommand, CanonicalOrderLeg
from trading_ai.order_management.order_recovery_service import OrderRecoveryService
from trading_ai.order_management.order_repository import JsonOrderRepository
from trading_ai.order_management.order_repository_policy import OrderRepositoryPolicy
from trading_ai.order_management.order_service import CanonicalOrderService


def create_and_persist(service, persistence, command):
    result = service.create(command)
    assert result.allowed and result.aggregate and result.event
    persistence.persist_created(result.aggregate, result.event)
    return result.aggregate


def transition_and_persist(service, persistence, aggregate, action, event_id, **kwargs):
    result = service.transition(aggregate, action, event_id=event_id, **kwargs)
    assert result.allowed and result.aggregate and result.event
    persistence.persist_transition(
        result.aggregate,
        result.event,
        expected_version=aggregate.version,
    )
    return result.aggregate


def main() -> None:
    future = date.today() + timedelta(days=45)
    mapper = InstrumentMapper()
    call = mapper.map({
        "asset_class": "OPTION",
        "underlying_symbol": "AAPL",
        "expiration": future.isoformat(),
        "strike": 200.0,
        "option_type": "CALL",
    })
    assert call.allowed

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
        lifecycle = CanonicalOrderService()
        group_repository = JsonOrderGroupRepository(root / "groups.json")
        recovery = OrderRecoveryService(root / "recovery.json")
        broker_execution = BrokerExecutionService(
            broker_service=broker_service,
            execution_adapter=execution_adapter,
            order_service=BrokerOrderService(),
            idempotency_registry=BrokerIdempotencyRegistry(root / "broker_idem.json"),
        )
        workflow = OrderGroupWorkflowService(
            repository=repository,
            persistence=persistence,
            group_repository=group_repository,
            recovery_service=recovery,
            lifecycle_service=lifecycle,
            broker_execution_services={"paper": broker_execution},
        )

        def command(aggregate_id, client_id, key, side, limit_price, root_id):
            return CanonicalOrderCommand(
                command_id=f"cmd-{aggregate_id}",
                command_type="CREATE",
                aggregate_id=aggregate_id,
                client_order_id=client_id,
                account_id="PAPER-001",
                idempotency_key=key,
                order_type="LIMIT",
                time_in_force="GTC",
                limit_price=limit_price,
                legs=(
                    CanonicalOrderLeg(
                        leg_id="leg-1",
                        symbol=call.canonical_symbol,
                        broker_symbol=call.broker_symbol,
                        asset_class="OPTION",
                        side=side,
                        quantity=1,
                        position_effect="OPEN" if "OPEN" in side else "CLOSE",
                    ),
                ),
                metadata={"root_aggregate_id": root_id},
            )

        entry = create_and_persist(
            lifecycle, persistence,
            command("entry-001", "entry-client", "entry-key", "BUY_TO_OPEN", 5.0, "entry-001"),
        )
        take_profit = create_and_persist(
            lifecycle, persistence,
            command("tp-001", "tp-client", "tp-key", "SELL_TO_CLOSE", 7.5, "entry-001"),
        )
        stop_loss = create_and_persist(
            lifecycle, persistence,
            command("sl-001", "sl-client", "sl-key", "SELL_TO_CLOSE", 3.5, "entry-001"),
        )

        # Align root ids for linkage validation.
        take_profit = replace(take_profit, root_aggregate_id="entry-001")
        stop_loss = replace(stop_loss, root_aggregate_id="entry-001")

        bracket = OrderGroupEngine().create_group(
            group_id="bracket-001",
            group_type="BRACKET",
            aggregates=(entry, take_profit, stop_loss),
            roles={
                "entry-001": "ENTRY",
                "tp-001": "TAKE_PROFIT",
                "sl-001": "STOP_LOSS",
            },
        )
        assert bracket.allowed and bracket.group
        group_repository.save(bracket.group)

        entry_live = repository.require("entry-001")
        for action, event_id in (
            ("VALIDATE", "entry-validate"),
            ("ROUTE", "entry-route"),
            ("SUBMIT", "entry-submit"),
            ("WORK", "entry-work"),
        ):
            entry_live = transition_and_persist(
                lifecycle, persistence, entry_live, action, event_id
            )
        entry_live = transition_and_persist(
            lifecycle, persistence, entry_live, "FILL", "entry-fill",
            filled_quantity=1, average_fill_price=5.0,
        )

        activated = workflow.activate_children(
            group_id="bracket-001",
            parent_aggregate_id="entry-001",
        )
        assert activated.allowed
        assert set(activated.aggregate_ids) == {"tp-001", "sl-001"}

        # Build an OCO group from the two exits.
        oco = OrderGroupEngine().create_group(
            group_id="oco-001",
            group_type="OCO",
            aggregates=(take_profit, stop_loss),
            roles={"tp-001": "MEMBER", "sl-001": "MEMBER"},
        )
        assert oco.allowed and oco.group
        group_repository.save(oco.group)

        # Submit both exit orders directly through fake broker and mirror broker ids.
        for aggregate_id in ("tp-001", "sl-001"):
            aggregate = repository.require(aggregate_id)
            for action, event_id in (
                ("VALIDATE", f"{aggregate_id}-validate"),
                ("ROUTE", f"{aggregate_id}-route"),
            ):
                aggregate = transition_and_persist(
                    lifecycle, persistence, aggregate, action, event_id
                )
            broker_order = broker_execution.submit(
                __import__(
                    "trading_ai.order_management.order_broker_mapper",
                    fromlist=["canonical_to_broker_order"],
                ).canonical_to_broker_order(
                    aggregate,
                    {"leg-1": call},
                )
            )
            assert broker_order.allowed
            aggregate = transition_and_persist(
                lifecycle, persistence, aggregate, "SUBMIT",
                f"{aggregate_id}-submit",
                broker_order_id=broker_order.broker_order_id,
            )
            aggregate = transition_and_persist(
                lifecycle, persistence, aggregate, "WORK",
                f"{aggregate_id}-work",
            )

        tp_live = repository.require("tp-001")
        tp_live = transition_and_persist(
            lifecycle, persistence, tp_live, "FILL", "tp-fill",
            filled_quantity=1, average_fill_price=7.5,
        )

        canceled = workflow.cancel_oco_siblings(
            group_id="oco-001",
            triggering_aggregate_id="tp-001",
            route_id="paper",
        )
        assert canceled.allowed
        assert canceled.aggregate_ids == ("sl-001",)
        assert repository.require("sl-001").state == "CANCELED"

        # Create a replaceable order and exercise recovery checkpoints.
        replace_order = create_and_persist(
            lifecycle, persistence,
            command("replace-001", "replace-client", "replace-key", "BUY_TO_OPEN", 4.5, "replace-001"),
        )
        aggregate = repository.require("replace-001")
        for action, event_id in (
            ("VALIDATE", "replace-validate"),
            ("ROUTE", "replace-route"),
        ):
            aggregate = transition_and_persist(
                lifecycle, persistence, aggregate, action, event_id
            )
        broker_result = broker_execution.submit(
            __import__(
                "trading_ai.order_management.order_broker_mapper",
                fromlist=["canonical_to_broker_order"],
            ).canonical_to_broker_order(
                aggregate,
                {"leg-1": call},
            )
        )
        assert broker_result.allowed
        aggregate = transition_and_persist(
            lifecycle, persistence, aggregate, "SUBMIT", "replace-submit",
            broker_order_id=broker_result.broker_order_id,
        )
        aggregate = transition_and_persist(
            lifecycle, persistence, aggregate, "WORK", "replace-work"
        )

        replaced = workflow.replace_order(
            aggregate_id="replace-001",
            route_id="paper",
            instrument_mappings={"leg-1": call},
            new_limit_price=4.25,
            new_stop_price=None,
        )
        assert replaced.allowed
        assert replaced.recovery_checkpoint is not None
        assert replaced.recovery_checkpoint.state == "COMPLETED"
        final = repository.require("replace-001")
        assert final.state == "REPLACED"
        assert final.replace_count == 1

        replay = persistence.replay("replace-001")
        assert replay.allowed
        assert replay.final_state == "REPLACED"

        valid, errors = persistence.verify_integrity()
        assert valid and errors == ()

        payload = dumps(replaced)
        assert '"state": "COMPLETED"' in payload
        assert '"action": "REPLACE"' in payload

    print(
        "All parent/child, bracket, OCO, cancel/replace, and "
        "recovery-governance assertions passed."
    )


if __name__ == "__main__":
    main()
