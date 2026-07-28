import pytest

from trading_ai.paper_trading.automated_lifecycle import (
    AutomatedOrderLifecyclePolicy,
)


def test_live_policy_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomatedOrderLifecyclePolicy(live_trading_enabled=True).validate()


def test_nonpaper_policy_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomatedOrderLifecyclePolicy(environment="LIVE").validate()


def test_partial_fill_threshold_cannot_be_shorter():
    with pytest.raises(ValueError, match="partial-fill"):
        AutomatedOrderLifecyclePolicy(
            stale_submitted_minutes=30,
            stale_partial_fill_minutes=20,
        ).validate()
