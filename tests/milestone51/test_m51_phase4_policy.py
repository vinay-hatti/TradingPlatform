import pytest

from trading_ai.paper_trading.automated_portfolio_management import (
    AutomatedPortfolioManagementPolicy,
)


def test_live_portfolio_policy_is_rejected():
    with pytest.raises(ValueError, match="live trading"):
        AutomatedPortfolioManagementPolicy(live_trading_enabled=True).validate()


def test_nonpaper_policy_is_rejected():
    with pytest.raises(ValueError, match="PAPER"):
        AutomatedPortfolioManagementPolicy(environment="LIVE").validate()
