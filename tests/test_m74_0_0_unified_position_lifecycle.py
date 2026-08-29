from __future__ import annotations

from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService


class RealTjxTradePlan:
    symbol = "TJX"
    legs_json = [
        {
            "side": "BUY",
            "quantity": 1,
            "option_right": "CALL",
            "strike": 160.0,
            "expiry": "2026-09-18",
            "option_symbol": "O:TJX260918C00160000",
        }
    ]


class RealTjxBrokerPosition:
    contract_id = 787047242
    symbol = "TJX"
    local_symbol = "TJX   260918C00160000"
    expiry = "20260918"
    strike = 160.0
    right = "C"


def test_m74_real_tjx_provider_identity_converges():
    match = BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(
        RealTjxTradePlan(), RealTjxBrokerPosition()
    )
    assert match == "OCC_OPTION_SYMBOL"


def test_m74_polygon_and_ibkr_option_identity_normalize_to_same_contract():
    normalize = BrokerPortfolioSynchronizationService._normalize_option_symbol
    assert normalize("O:TJX260918C00160000") == "O:TJX260918C00160000"
    assert normalize("TJX   260918C00160000") == "O:TJX260918C00160000"


def test_m74_structural_fallback_requires_complete_exact_option_tuple():
    class Plan:
        symbol = "TJX"
        legs_json = [{"expiry": "2026-09-18", "strike": 160.0, "option_right": "CALL"}]

    class Broker:
        contract_id = 999
        symbol = "TJX"
        local_symbol = ""
        expiry = "20260918"
        strike = 160.0
        right = "C"

    assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(Plan(), Broker()) == "OPTION_TUPLE"
    Broker.right = "P"
    assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(Plan(), Broker()) is None
