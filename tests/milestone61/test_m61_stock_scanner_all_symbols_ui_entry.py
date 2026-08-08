from pathlib import Path

from trading_ai.stock_intelligence import StockIntelligenceService


def _rows(n=180, start=100.0, step=0.35, vol=1000.0):
    return [
        {
            "open": start + i * step - 0.1,
            "high": start + i * step + 0.5,
            "low": start + i * step - 0.5,
            "close": start + i * step,
            "volume": vol + i * 7,
        }
        for i in range(n)
    ]


def test_market_ingestion_publishes_all_asset_classes_and_no_top_cap_by_default():
    text = Path("scripts/run_market_ingestion.py").read_text()
    assert "_publish_stock_intelligence(args, symbols)" in text
    assert 'default=0, help="Maximum published candidates; 0 publishes every successfully analyzed symbol.' in text
    assert "top=None if args.stock_intelligence_top <= 0" in text
    assert "Defaults to all ingested equities, ETFs, and indexes." in text


def test_publication_and_api_support_full_canonical_universe():
    service = Path("src/trading_ai/stock_intelligence/publication_service.py").read_text()
    publication = Path("src/trading_ai/stock_intelligence/publication.py").read_text()
    router = Path("src/trading_ai/stock_intelligence/router.py").read_text()
    assert "minimum_score: float = 0.0" in service
    assert "top: int | None = None" in service
    assert "limit: int = 2000" in publication
    assert "le=5000" in router


def test_stock_scanner_has_header_filters_and_expandable_details():
    text = Path("ui/workstation/src/StockIntelligenceScannerPage.tsx").read_text()
    assert "stock-filter-row" in text
    assert "headerSelect('category'" in text
    assert "headerSelect('direction'" in text
    assert "expandedId" in text
    assert "stock-expanded-row" in text
    assert "Entry rationale" in text
    assert "Candidate details" not in text


def test_dynamic_entry_zone_is_bounded_by_atr_and_price():
    profile = StockIntelligenceService().analyze(
        "TEST",
        {"1d": _rows(), "1w": _rows(step=0.25), "1mo": _rows(step=0.15)},
        "2026-08-04T00:00:00Z",
    )
    entry = profile.trade_plan.entry
    state = profile.timeframe_states[profile.primary_timeframe]
    width = entry.zone_high - entry.zone_low
    assert width > 0
    assert width <= max(state.close * 0.0061, 0.02)
    assert width <= state.atr * 0.36 + 0.02
    assert entry.zone_low <= entry.preferred_entry <= entry.zone_high
