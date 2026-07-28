import pytest

from trading_ai.paper_trading.automated_position_management import (
    AutomatedPositionManagementPolicy,
)


def test_live_trading_policy_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomatedPositionManagementPolicy(live_trading_enabled=True).validate()


def test_nonpaper_policy_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomatedPositionManagementPolicy(environment="LIVE").validate()


def test_exit_orders_are_limit_only():
    with pytest.raises(ValueError, match="LIMIT"):
        AutomatedPositionManagementPolicy(exit_order_type="MARKET").validate()
