import pytest
from trading_ai.paper_trading.operational_readiness import OperationalReadinessPolicy


def test_live_readiness_rejected():
    with pytest.raises(ValueError, match="live trading"):
        OperationalReadinessPolicy(live_trading_enabled=True).validate()


def test_nonpaper_readiness_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        OperationalReadinessPolicy(environment="LIVE").validate()
