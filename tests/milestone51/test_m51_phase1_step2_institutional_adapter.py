from trading_ai.paper_trading.automated_order_handoff import (
    InstitutionalDecisionHandoffAdapter,
)


def payload():
    return {
        "run": {
            "scan_id": "scan-1",
            "decisions_by_symbol": {
                "AAPL": {
                    "available": True,
                    "allowed": True,
                    "selected": True,
                    "action": "BUY",
                    "readiness": "READY",
                    "strategy": "TREND",
                    "decision_confidence": 80,
                    "calibrated_probability": 0.65,
                },
                "MSFT": {
                    "available": True,
                    "allowed": False,
                    "selected": False,
                    "action": "HOLD",
                    "readiness": "REVIEW",
                    "strategy": "NONE",
                    "decision_confidence": 40,
                    "calibrated_probability": 0.4,
                },
            },
        },
        "candidates": [
            {
                "symbol": "AAPL",
                "source": {
                    "price": 200,
                    "metadata": {
                        "asset_class": "EQUITY",
                        "risk_gateway_allowed": True,
                        "primary_exchange": "NASDAQ",
                    },
                },
            },
            {
                "symbol": "MSFT",
                "source": {"price": 500, "metadata": {}},
            },
        ],
    }


def test_selected_institutional_decision_converts_to_step1_candidate():
    converted = InstitutionalDecisionHandoffAdapter().convert_payload(payload())
    by_symbol = {item.symbol: item for item in converted}
    aapl = by_symbol["AAPL"]
    assert aapl.accepted is True
    assert aapl.candidate is not None
    assert aapl.candidate.symbol == "AAPL"
    assert aapl.candidate.limit_price == 199.0
    assert aapl.candidate.institutional_allowed is True
    assert aapl.candidate.risk_gateway_allowed is True


def test_nonselected_or_disallowed_decision_is_rejected():
    converted = InstitutionalDecisionHandoffAdapter().convert_payload(payload())
    msft = {item.symbol: item for item in converted}["MSFT"]
    assert msft.accepted is False
    assert "INSTITUTIONAL_DECISION_NOT_ALLOWED" in msft.rejection_reasons
    assert "INSTITUTIONAL_DECISION_NOT_SELECTED" in msft.rejection_reasons


def test_option_requires_executable_contract_fields():
    value = payload()
    value["candidates"][0]["source"]["metadata"]["asset_class"] = "OPTION"
    converted = InstitutionalDecisionHandoffAdapter().convert_payload(value)
    aapl = {item.symbol: item for item in converted}["AAPL"]
    assert aapl.accepted is False
    assert "OPTION_EXPIRY_NOT_AVAILABLE" in aapl.rejection_reasons
    assert "OPTION_STRIKE_NOT_AVAILABLE" in aapl.rejection_reasons
