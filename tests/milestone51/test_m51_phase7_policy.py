import pytest

from trading_ai.paper_trading.automation_observability import (
    AutomationObservabilityPolicy,
)


def test_live_observability_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomationObservabilityPolicy(live_trading_enabled=True).validate()


def test_nonpaper_observability_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomationObservabilityPolicy(environment="LIVE").validate()
