from pathlib import Path

SERVICE = Path("src/trading_ai/option_valuation_intelligence/events/institutional_service.py")


def test_event_intelligence_uses_canonical_price_history_table():
    text = SERVICE.read_text()
    assert "FROM price_history" in text
    assert "FROM market_data" not in text


def test_event_intelligence_handles_legacy_text_event_dates():
    text = SERVICE.read_text()
    assert "SUBSTRING(event_date FROM 1 FOR 10)::date" in text
    assert "event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'" in text


def test_spot_lookup_is_case_insensitive():
    text = SERVICE.read_text()
    assert "UPPER(symbol)=UPPER(:s)" in text
