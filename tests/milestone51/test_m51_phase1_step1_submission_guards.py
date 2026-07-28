import pytest

from trading_ai.paper_trading.automated_order_handoff import (
    AutomatedPaperOrderCandidate,
    AutomatedPaperOrderHandoffPolicy,
)


def test_policy_is_irreversibly_paper_only():
    with pytest.raises(ValueError, match="PAPER"):
        AutomatedPaperOrderHandoffPolicy(environment="LIVE").validate()
    with pytest.raises(ValueError, match="live trading"):
        AutomatedPaperOrderHandoffPolicy(live_trading_enabled=True).validate()


def test_candidate_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unsupported candidate fields"):
        AutomatedPaperOrderCandidate.from_dict({
            "candidate_id": "x",
            "portfolio_id": "PAPER-PRIMARY",
            "symbol": "AAPL",
            "asset_class": "EQUITY",
            "side": "BUY",
            "quantity": 1,
            "unknown": True,
        })
