from datetime import date
from trading_ai.option_valuation_intelligence.events.contracts import SourceEventRecord
from trading_ai.option_valuation_intelligence.events.service import _canonical_payload, _hash

def test_stable_source_key_and_content_hash_are_deterministic():
    r=SourceEventRecord('ALPHA_VANTAGE','ALPHAVANTAGE:EARNINGS:AAPL:2026-09-30','AAPL','EARNINGS',date(2026,10,29),'Apple Earnings',event_session='POST_MARKET')
    assert _hash(_canonical_payload(r)) == _hash(_canonical_payload(r))

def test_changed_date_changes_hash_but_not_source_identity():
    a=SourceEventRecord('ALPHA_VANTAGE','ALPHAVANTAGE:EARNINGS:AAPL:2026-09-30','AAPL','EARNINGS',date(2026,10,29),'Apple Earnings')
    b=SourceEventRecord('ALPHA_VANTAGE','ALPHAVANTAGE:EARNINGS:AAPL:2026-09-30','AAPL','EARNINGS',date(2026,10,30),'Apple Earnings')
    assert a.source_event_key == b.source_event_key
    assert _hash(_canonical_payload(a)) != _hash(_canonical_payload(b))
