from pathlib import Path


def test_event_date_query_casts_legacy_varchar_to_date():
    path = Path("src/trading_ai/option_valuation_intelligence/events/institutional_service.py")
    source = path.read_text(encoding="utf-8")
    assert "SUBSTRING(event_date FROM 1 FOR 10)::date" in source
    assert "event_date>=CURRENT_DATE" not in source
    assert "event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'" in source
