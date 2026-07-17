from trading_ai.order_management.order_profile import CanonicalOrderCommand, CanonicalOrderLeg
from trading_ai.order_management.order_serialization import dumps
from trading_ai.order_management.order_service import CanonicalOrderService

def main():
    service = CanonicalOrderService()
    legs = (
        CanonicalOrderLeg(
            leg_id="leg-1",
            symbol="AAPL  260821C00200000",
            broker_symbol="AAPL  260821C00200000",
            asset_class="OPTION",
            side="BUY_TO_OPEN",
            quantity=2,
            position_effect="OPEN",
        ),
    )
    command = CanonicalOrderCommand(
        command_id="cmd-create-001", command_type="CREATE",
        aggregate_id="agg-order-001", client_order_id="client-order-001",
        account_id="PAPER-001", idempotency_key="idem-order-001",
        order_type="LIMIT", time_in_force="DAY", limit_price=5.00,
        strategy_name="LONG_CALL", legs=legs,
    )
    created = service.create(command)
    assert created.allowed and created.aggregate and created.event
    assert created.aggregate.state == "NEW"
    assert created.aggregate.version == 1
    assert created.aggregate.total_quantity == 2
    assert created.event.event_type == "ORDER_CREATED"

    aggregate = created.aggregate
    for action, event_id, expected in (
        ("VALIDATE","evt-validate-001","VALIDATED"),
        ("ROUTE","evt-route-001","ROUTED"),
        ("SUBMIT","evt-submit-001","SUBMITTED"),
        ("ACKNOWLEDGE","evt-ack-001","ACKNOWLEDGED"),
        ("WORK","evt-work-001","WORKING"),
    ):
        result = service.transition(
            aggregate, action, event_id=event_id,
            broker_order_id="broker-order-001" if action == "SUBMIT" else None,
        )
        assert result.allowed and result.aggregate
        assert result.aggregate.state == expected
        aggregate = result.aggregate

    partial = service.transition(
        aggregate, "PARTIAL_FILL", event_id="evt-partial",
        filled_quantity=1, average_fill_price=4.90,
    )
    assert partial.allowed and partial.aggregate and partial.event
    assert partial.aggregate.state == "PARTIALLY_FILLED"
    assert partial.aggregate.remaining_quantity == 1
    assert partial.event.event_type == "ORDER_PARTIALLY_FILLED"

    regression = service.transition(
        partial.aggregate, "PARTIAL_FILL",
        event_id="evt-regression", filled_quantity=0.5,
    )
    assert not regression.allowed
    assert "FILLED_QUANTITY_MONOTONIC" in regression.rejection_reasons

    overfill = service.transition(
        partial.aggregate, "FILL", event_id="evt-overfill", filled_quantity=3,
    )
    assert not overfill.allowed
    assert "ORDER_OVERFILL" in overfill.rejection_reasons

    cancel_pending = service.transition(
        partial.aggregate, "CANCEL_REQUEST",
        event_id="evt-cancel-request", reason="USER_REQUEST",
    )
    assert cancel_pending.allowed and cancel_pending.aggregate
    assert cancel_pending.aggregate.state == "CANCEL_PENDING"

    canceled = service.transition(
        cancel_pending.aggregate, "CANCEL", event_id="evt-cancel",
    )
    assert canceled.allowed and canceled.aggregate
    assert canceled.aggregate.state == "CANCELED"
    assert canceled.aggregate.terminal

    terminal = service.transition(
        canceled.aggregate, "WORK", event_id="evt-invalid-terminal",
    )
    assert not terminal.allowed
    assert "TRANSITION_DEFINED" in terminal.rejection_reasons
    assert "TERMINAL_TRANSITION" in terminal.rejection_reasons

    second = service.create(CanonicalOrderCommand(
        command_id="cmd-create-002", command_type="CREATE",
        aggregate_id="agg-order-002", client_order_id="client-order-002",
        account_id="PAPER-001", idempotency_key="idem-order-002",
        order_type="LIMIT", time_in_force="DAY", limit_price=5.25, legs=legs,
    ))
    assert second.aggregate
    aggregate = second.aggregate
    for action, event_id in (
        ("VALIDATE","evt2-validate"),("ROUTE","evt2-route"),
        ("SUBMIT","evt2-submit"),("WORK","evt2-work"),
    ):
        result = service.transition(aggregate, action, event_id=event_id)
        assert result.allowed and result.aggregate
        aggregate = result.aggregate

    filled = service.transition(
        aggregate, "FILL", event_id="evt2-fill",
        filled_quantity=2, average_fill_price=5.10,
    )
    assert filled.allowed and filled.aggregate and filled.event
    assert filled.aggregate.state == "FILLED"
    assert filled.aggregate.remaining_quantity == 0
    assert filled.aggregate.terminal

    payload = dumps(filled)
    assert '"state": "FILLED"' in payload
    assert '"event_type": "ORDER_FILLED"' in payload
    assert '"aggregate_version": 6' in payload

    invalid = service.create(CanonicalOrderCommand(
        command_id="cmd-invalid", command_type="CREATE",
        aggregate_id="agg-invalid", client_order_id="client-invalid",
        account_id="PAPER-001", idempotency_key="idem-invalid",
        order_type="LIMIT", time_in_force="DAY", legs=legs,
    ))
    assert not invalid.allowed
    assert "LIMIT_PRICE" in invalid.rejection_reasons

    print("All canonical order aggregate, lifecycle state-machine, and event-contract assertions passed.")

if __name__ == "__main__":
    main()
