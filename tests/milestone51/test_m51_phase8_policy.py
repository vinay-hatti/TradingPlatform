import pytest
from trading_ai.paper_trading.automation_recovery import AutomationRecoveryPolicy


def test_live_recovery_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomationRecoveryPolicy(live_trading_enabled=True).validate()


def test_submit_replay_rejected():
    with pytest.raises(ValueError, match="submit replay"):
        AutomationRecoveryPolicy(permit_submit_replay=True).validate()
