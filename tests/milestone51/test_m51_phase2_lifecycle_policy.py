from datetime import datetime, timedelta, timezone

from trading_ai.paper_trading.automated_lifecycle import (
    AutomatedOrderLifecycleEngine,
    AutomatedOrderLifecyclePolicy,
    BrokerOrderLifecycleSnapshot,
)


NOW = datetime(2026, 7, 26, 20, 0, tzinfo=timezone.utc)


def order(status="SUBMITTED", minutes=10, filled=0, remaining=1):
    timestamp = (NOW - timedelta(minutes=minutes)).isoformat()
    return BrokerOrderLifecycleSnapshot(
        aggregate_id="A1",
        broker_order_id=1,
        symbol="AAPL",
        security_type="STK",
        side="BUY",
        quantity=1,
        status=status,
        filled_quantity=filled,
        remaining_quantity=remaining,
        average_fill_price=0,
        submitted_at=timestamp,
        updated_at=timestamp,
    )


def test_active_order_is_monitored():
    action = AutomatedOrderLifecycleEngine().classify(order(), now=NOW)
    assert action.action == "MONITOR"


def test_stale_order_requires_cancel_review_by_default():
    action = AutomatedOrderLifecycleEngine().classify(
        order(minutes=45), now=NOW
    )
    assert action.action == "CANCEL_STALE_ORDER"
    assert action.allowed is False
    assert action.confirmation_required is True


def test_enabled_policy_allows_stale_cancel_action():
    engine = AutomatedOrderLifecycleEngine(
        AutomatedOrderLifecyclePolicy(automatic_cancellation_enabled=True)
    )
    action = engine.classify(order(minutes=45), now=NOW)
    assert action.allowed is True


def test_terminal_order_never_cancels():
    action = AutomatedOrderLifecycleEngine().classify(
        order(status="Cancelled", minutes=300, remaining=0), now=NOW
    )
    assert action.action == "NO_ACTION"
    assert action.reason == "ORDER_TERMINAL"
