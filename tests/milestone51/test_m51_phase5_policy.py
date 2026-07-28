import pytest

from trading_ai.paper_trading.automation_control_plane import (
    AutomationControlPlanePolicy,
)


def test_live_control_plane_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomationControlPlanePolicy(live_trading_enabled=True).validate()


def test_nonpaper_control_plane_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomationControlPlanePolicy(environment="LIVE").validate()
