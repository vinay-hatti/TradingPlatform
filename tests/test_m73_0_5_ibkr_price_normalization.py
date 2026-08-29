from pathlib import Path
from trading_ai.broker.ibkr.price_normalization import select_price_increment,snap_limit_price,normalize_limit_price


def test_buy_prices_round_down_without_worsening_governed_limit():
    assert snap_limit_price(10.4075,0.05,'BUY')==10.4
    assert snap_limit_price(2.9375,0.01,'BUY')==2.93
    assert snap_limit_price(13.125,0.05,'BUY')==13.1

def test_sell_prices_round_up_without_sacrificing_credit():
    assert snap_limit_price(4.2934,0.05,'SELL')==4.3

def test_price_dependent_market_rule_band():
    rules=[{'low_edge':0,'increment':0.01},{'low_edge':3,'increment':0.05}]
    assert select_price_increment(2.9375,rules,0.01)==0.01
    assert select_price_increment(10.4075,rules,0.01)==0.05

def test_contract_min_tick_fallback():
    assert select_price_increment(10.4075,[],0.05)==0.05

def test_normalization_evidence():
    out=normalize_limit_price(10.4075,'BUY',[{'low_edge':0,'increment':0.05}],0.01)
    assert out['normalized_price']==10.4
    assert out['increment']==0.05
    assert out['changed'] is True

def test_source_wires_initial_and_reprice_normalization():
    root=Path(__file__).resolve().parents[1]
    ws=(root/'src/trading_ai/execution_workspace/service.py').read_text()
    transport=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
    assert ws.count('normalize_option_limit_price')>=2
    assert 'reqMarketRule' in transport
    assert 'marketRuleIds' in transport
