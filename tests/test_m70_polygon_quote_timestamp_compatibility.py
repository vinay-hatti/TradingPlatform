from trading_ai.execution_intelligence.provider import PolygonDirectExecutionQuoteProvider
from trading_ai.execution_intelligence.service import _age


def test_polygon_option_snapshot_last_updated_nanoseconds_is_quote_timestamp():
    provider=PolygonDirectExecutionQuoteProvider.__new__(PolygonDirectExecutionQuoteProvider)
    provider._get=lambda *a,**k:{'results':{
        'last_quote':{'bid':6.7,'ask':7.2,'bid_size':10,'ask_size':12,'last_updated':1786127374123456789},
        'last_trade':{'price':6.95},'day':{'volume':100},'greeks':{},'underlying_asset':{'price':220.0}
    }}
    q=provider.option_quote('COF','O:COF260918C00220000')
    assert q.quote_timestamp == '2026-08-07T18:29:34.123457+00:00'


def test_polygon_option_snapshot_legacy_timestamp_fallback_still_supported():
    provider=PolygonDirectExecutionQuoteProvider.__new__(PolygonDirectExecutionQuoteProvider)
    provider._get=lambda *a,**k:{'results':{
        'last_quote':{'bid':6.7,'ask':7.2,'sip_timestamp':1786127374123456789},
        'last_trade':{'price':6.95},'day':{},'greeks':{},'underlying_asset':{}
    }}
    q=provider.option_quote('COF','O:COF260918C00220000')
    assert q.quote_timestamp == '2026-08-07T18:29:34.123457+00:00'


def test_missing_quote_timestamp_does_not_fabricate_billion_second_age():
    assert _age(None) is None
    assert _age('') is None
