from datetime import datetime, timezone

from trading_ai.paper_trading.automated_position_management import (
    AutomatedPositionManagementEngine,
    ManagedPaperPosition,
)


def test_option_near_expiry_generates_exit():
    position = ManagedPaperPosition(
        position_id="P1",
        portfolio_id="PAPER-PRIMARY",
        aggregate_id="A1",
        symbol="AAPL",
        security_type="OPT",
        direction="LONG",
        quantity=1,
        average_entry_price=5,
        current_price=5,
        opened_at="2026-07-26T10:00:00+00:00",
        expiry="20260728",
        strike=200,
        right="C",
    )
    assessment = AutomatedPositionManagementEngine().assess(
        position,
        now=datetime(2026, 7, 26, 20, 0, tzinfo=timezone.utc),
    )
    assert assessment.action == "EXIT"
    assert assessment.trigger == "OPTION_EXPIRY_WINDOW"
