from datetime import date, timedelta
from types import SimpleNamespace
from trading_ai.option_valuation_intelligence.context import build_relative_context, contract_features, event_context


def rec(cid, iv, symbol='AAA', sector='TECH'):
    row=SimpleNamespace(contract_recommendation_id=cid,liquidity_score=80,payload_json={'strategy':'LONG_CALL','legs':[{'side':'BUY','bid':2,'ask':2.1,'strike':100,'right':'C','dte':30,'implied_volatility':iv}]})
    return contract_features(row,symbol,sector,100)


def test_relative_value_peer_divergence_is_governed():
    fs=[rec('a',.20,'AAA'),rec('b',.30,'BBB'),rec('c',.32,'CCC')]
    ctx=build_relative_context(fs)['a']
    assert ctx['available'] is True
    assert ctx['peer_median_iv']>.20
    assert ctx['relationship_regime']=='DISCOUNTED_TO_PEERS'


def test_event_move_mispricing_context():
    event=SimpleNamespace(status='ACTIVE',symbol='AAA',event_type='EARNINGS',event_date=(date.today()+timedelta(days=10)).isoformat(),expected_move_pct=8.0,historical_move_pct=7.0,confidence=80,source='TEST',event_id='e1')
    ctx=event_context('AAA',{},[event],.30,date.today())
    assert ctx['available'] is True
    assert ctx['expected_move_pct']==8.0
    assert ctx['event_type']=='EARNINGS'
    assert ctx['score']>50
