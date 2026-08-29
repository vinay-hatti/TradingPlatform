from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_installed_backend_service_exists():
    p=ROOT/"src/trading_ai/stock_intelligence/cyclical_seasonality_presentation.py"
    assert p.exists()
    x=p.read_text()
    assert "RESEARCH_ONLY_NOT_SHADOW_CERTIFIED" in x
    assert "current_walk_forward_matches" in x

def test_installed_router_enrichment_exists():
    x=(ROOT/"src/trading_ai/stock_intelligence/router.py").read_text()
    assert 'value["cyclical_seasonality"]' in x
    assert "CyclicalSeasonalityPresentationService" in x

def test_installed_ui_location_and_governance():
    x=(ROOT/"ui/workstation/src/StockIntelligenceScannerPage.tsx").read_text()
    assert "Cycles &amp; seasonality intelligence" in x
    assert "Not shadow certified" in x
    assert x.index("Cycles &amp; seasonality intelligence") < x.index("Dynamic trade plan")
