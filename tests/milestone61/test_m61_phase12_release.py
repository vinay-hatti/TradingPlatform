from pathlib import Path

from trading_ai.database.base import Base
import trading_ai.stock_intelligence.models  # noqa: F401
from trading_ai.stock_intelligence.option_integration import UnderlyingOptionIntegrationPolicy


def test_production_api_registers_stock_intelligence_routes():
    text = Path("src/trading_ai/production_api/app.py").read_text()
    assert "stock_intelligence_router" in text
    assert "app.include_router(stock_intelligence_router)" in text
    router = Path("src/trading_ai/stock_intelligence/router.py").read_text()
    assert '@router.get("/candidates"' in router
    assert '@router.get("/candidates/{candidate_id}"' in router


def test_all_m61_tables_are_registered():
    names = set(Base.metadata.tables)
    assert "stock_position_intelligence_snapshots" in names
    assert "stock_outcome_observations" in names
    assert "stock_management_policy_performance" in names


def test_option_integration_remains_disabled_by_default():
    assert UnderlyingOptionIntegrationPolicy().enabled is False


def test_migration_attaches_to_m59_head():
    text = Path("migrations/versions/m61_001_stock_intelligence.py").read_text()
    assert 'down_revision="20260803_m59"' in text


def test_stock_scanner_operational_script_exists():
    text = Path("scripts/run_m61_stock_intelligence_scanner.py").read_text()
    assert "StockIntelligencePublicationService" in text
    assert "StockPublicationRequest" in text


def test_daily_scan_has_explicit_activation_flag():
    text = Path("scripts/run_daily_scan.py").read_text()
    assert "--enable-stock-intelligence" in text
    assert "StockIntelligenceOptionProvider" in text
