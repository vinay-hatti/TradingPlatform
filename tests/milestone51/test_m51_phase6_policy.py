import pytest

from trading_ai.paper_trading.automation_scheduler import (
    AutomationSchedulerPolicy,
)


def test_live_scheduler_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomationSchedulerPolicy(live_trading_enabled=True).validate()


def test_nonpaper_scheduler_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomationSchedulerPolicy(environment="LIVE").validate()
