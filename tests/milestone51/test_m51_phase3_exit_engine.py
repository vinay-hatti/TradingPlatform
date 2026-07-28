from datetime import datetime, timezone

from trading_ai.paper_trading.automated_position_management import (
    AutomatedPositionManagementEngine,
    ManagedPaperPosition,
)


NOW = datetime(2026, 7, 26, 20, 0, tzinfo=timezone.utc)


def position(**updates):
    values = dict(
        position_id="P1",
        portfolio_id="PAPER-PRIMARY",
        aggregate_id="A1",
        symbol="AAPL",
        security_type="STK",
        direction="LONG",
        quantity=1,
        average_entry_price=100,
        current_price=105,
        opened_at="2026-07-26T19:00:00+00:00",
    )
    values.update(updates)
    return ManagedPaperPosition(**values)


def test_take_profit_generates_sell_exit():
    engine = AutomatedPositionManagementEngine()
    assessment = engine.assess(position(current_price=125), now=NOW)
    assert assessment.action == "EXIT"
    assert assessment.trigger == "TAKE_PROFIT"
    intent = engine.intent(position(current_price=125), assessment)
    assert intent.side == "SELL"
    assert intent.order_type == "LIMIT"


def test_stop_loss_generates_critical_exit():
    assessment = AutomatedPositionManagementEngine().assess(
        position(current_price=85), now=NOW
    )
    assert assessment.action == "EXIT"
    assert assessment.trigger == "STOP_LOSS"
    assert assessment.urgency == "CRITICAL"


def test_small_gain_is_monitored():
    assessment = AutomatedPositionManagementEngine().assess(
        position(current_price=105), now=NOW
    )
    assert assessment.action == "MONITOR"
    assert assessment.trigger == "NONE"


def test_missing_market_price_blocks_exit():
    assessment = AutomatedPositionManagementEngine().assess(
        position(current_price=0), now=NOW
    )
    assert assessment.allowed is False
    assert "MARKET_PRICE_NOT_AVAILABLE" in assessment.rejection_reasons
