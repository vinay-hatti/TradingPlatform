from datetime import date
from pathlib import Path

from trading_ai.stock_intelligence.publication_service import StockIntelligencePublicationService


def test_market_ingestion_exposes_stock_publication_controls():
    text = Path("scripts/run_market_ingestion.py").read_text()
    for flag in (
        "--skip-stock-intelligence",
        "--require-stock-intelligence",
        "--stock-intelligence-publication-name",
        "--stock-intelligence-symbols",
        "--stock-intelligence-minimum-score",
        "--stock-intelligence-top",
        "--stock-intelligence-lookback-days",
    ):
        assert flag in text
    assert "_publish_stock_intelligence" in text
    assert "stock_publication=stock_publication" in text


def test_shared_publication_service_is_used_by_both_entry_points():
    market_script = Path("scripts/run_market_ingestion.py").read_text()
    standalone = Path("scripts/run_m61_stock_intelligence_scanner.py").read_text()
    assert "StockIntelligencePublicationService" in market_script
    assert "StockIntelligencePublicationService" in standalone
    assert "subprocess" not in standalone


def test_monthly_aggregation_uses_calendar_month_ohlcv():
    rows = [
        {"date": "2026-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
        {"date": "2026-01-30", "open": 11, "high": 15, "low": 10, "close": 14, "volume": 200},
        {"date": "2026-02-02", "open": 14, "high": 16, "low": 13, "close": 15, "volume": 300},
    ]
    values = StockIntelligencePublicationService._aggregate(rows, "month")
    assert values == [
        {"date": "2026-01-30", "open": 10, "high": 15, "low": 9, "close": 14, "volume": 300},
        {"date": "2026-02-02", "open": 14, "high": 16, "low": 13, "close": 15, "volume": 300},
    ]


def test_previous_valid_publication_is_preserved_for_readers():
    text = Path("src/trading_ai/stock_intelligence/publication.py").read_text()
    assert 'status.in_(("READY", "DEGRADED"))' in text


def test_orchestrator_persists_market_ingestion_lineage():
    text = Path("src/trading_ai/stock_intelligence/orchestration.py").read_text()
    assert "lineage_payload" in text
    assert '"lineage": lineage_payload' in text
