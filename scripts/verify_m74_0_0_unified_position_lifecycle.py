from pathlib import Path

from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService


class TradePlan:
    symbol = "TJX"
    legs_json = [{
        "side": "BUY",
        "quantity": 1,
        "option_right": "CALL",
        "strike": 160.0,
        "expiry": "2026-09-18",
        "option_symbol": "O:TJX260918C00160000",
    }]


class Broker:
    contract_id = 787047242
    symbol = "TJX"
    local_symbol = "TJX   260918C00160000"
    expiry = "20260918"
    strike = 160.0
    right = "C"


assert AutonomousPositionManagementService.VERSION == "M74.0.0-UNIFIED-POSITION-LIFECYCLE-1.0"
assert BrokerPortfolioSynchronizationService._normalize_option_symbol(TradePlan.legs_json[0]["option_symbol"]) == "O:TJX260918C00160000"
assert BrokerPortfolioSynchronizationService._normalize_option_symbol(Broker.local_symbol) == "O:TJX260918C00160000"
assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(TradePlan(), Broker()) == "OCC_OPTION_SYMBOL"

source = Path("src/trading_ai/broker_portfolio_sync/service.py").read_text()
for token in (
    "OCC_OPTION_SYMBOL",
    "OPTION_TUPLE",
    "_retire_superseded_managed_projection",
    "Canonical managed-position lineage recovered",
    "managed_position_id = managed.position_id",
):
    assert token in source, token

print("M74.0.0 unified position lifecycle verification: PASSED")
