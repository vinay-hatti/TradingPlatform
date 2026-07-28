from trading_ai.paper_trading.automated_lifecycle import (
    AutomatedOrderLifecycleEngine,
    BrokerExecutionSnapshot,
)


def execution(execution_id, side, quantity, price, when):
    return BrokerExecutionSnapshot(
        execution_id=execution_id,
        aggregate_id="A1",
        broker_order_id=1,
        symbol="AAPL",
        security_type="STK",
        side=side,
        quantity=quantity,
        price=price,
        commission=1.0,
        currency="USD",
        exchange="NASDAQ",
        executed_at=when,
    )


def test_partial_fills_project_single_idempotent_position():
    engine = AutomatedOrderLifecycleEngine()
    rows = [
        execution("E1", "BUY", 1, 100, "2026-07-26T10:00:00+00:00"),
        execution("E2", "BUY", 1, 102, "2026-07-26T10:01:00+00:00"),
    ]
    first = engine.project_positions("PAPER-PRIMARY", rows)
    second = engine.project_positions("PAPER-PRIMARY", list(reversed(rows)))
    assert first == second
    assert first[0].quantity == 2
    assert first[0].average_entry_price == 101
    assert first[0].total_commission == 2


def test_offsetting_execution_closes_projection():
    engine = AutomatedOrderLifecycleEngine()
    rows = [
        execution("E1", "BUY", 1, 100, "2026-07-26T10:00:00+00:00"),
        execution("E2", "SELL", 1, 110, "2026-07-26T11:00:00+00:00"),
    ]
    projection = engine.project_positions("PAPER-PRIMARY", rows)[0]
    assert projection.status == "CLOSED"
    assert projection.direction == "FLAT"
    assert projection.quantity == 0
