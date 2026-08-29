from datetime import datetime,timezone

from trading_ai.autonomous_position_management.quotes import polygon_option_symbol_from_local_symbol
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.broker_portfolio_sync.service import _normalized_broker_unit_price


def test_ibkr_option_average_cost_normalized_once():
    assert round(_normalized_broker_unit_price('OPT',800.7873,100),6)==8.007873
    assert round(_normalized_broker_unit_price('OPT',16351.7003,100),6)==163.517003
    assert _normalized_broker_unit_price('STK',123.45,1)==123.45


def test_occ_local_symbol_is_canonical_polygon_identity():
    assert polygon_option_symbol_from_local_symbol('SPX   260918C07725000')=='O:SPX260918C07725000'
    assert polygon_option_symbol_from_local_symbol('ABNB  260918C00175000')=='O:ABNB260918C00175000'


def test_market_closed_weekend_is_idle_classification():
    saturday=datetime(2026,8,8,15,0,tzinfo=timezone.utc)
    assert AutonomousPositionManagementService._market_session_state(saturday)=='MARKET_CLOSED'


def test_market_open_weekday_classification():
    monday=datetime(2026,8,10,15,0,tzinfo=timezone.utc)  # 11:00 ET
    assert AutonomousPositionManagementService._market_session_state(monday)=='MARKET_OPEN'
