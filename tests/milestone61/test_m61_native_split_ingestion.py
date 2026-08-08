from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_split_scripts_do_not_delegate_to_core_main():
    for name in ("ingest_underlying_data.py", "ingest_options_data.py"):
        text = (ROOT / "scripts" / name).read_text()
        assert "core.main(" not in text
        assert "finalize_shared_state(" in text


def test_underlying_is_authoritative_for_trend_refresh():
    text = (ROOT / "scripts" / "ingest_underlying_data.py").read_text()
    assert "args.force_trend_refresh = True" in text
    assert "run_trend=True" in text


def test_options_owns_options_and_dealer_stages():
    text = (ROOT / "scripts" / "ingest_options_data.py").read_text()
    assert "OptionHistoryIngestionService" in text
    assert "_run_dealer_positioning" in text
    assert "refresh_trend_intelligence" in text


def test_shared_finalizer_publishes_market_and_stock_state():
    text = (ROOT / "scripts" / "ingestion_split_common.py").read_text()
    assert "_run_market_overview" in text
    assert "_run_market_intelligence" in text
    assert "_publish_scanner_state" in text
    assert "_publish_stock_intelligence" in text
