from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text()

def test_stock_publication_exposes_reference_and_certification():
    s=read('src/trading_ai/stock_intelligence/publication.py')
    assert 'underlying_reference_price' in s
    assert 'trade_plan_certification_status' in s
    assert 'trade_plan_quality_score' in s

def test_institutional_options_requires_certification():
    s=read('src/trading_ai/institutional_options/opportunity_ingestion.py')
    assert 'TRADE_PLAN_CERTIFICATION_MISSING' in s
    assert 'TRADE_PLAN_CERTIFICATION_FAILED' in s

def test_certification_propagates_to_trade_builder_and_execution():
    h=read('src/trading_ai/institutional_options/handoff.py')
    e=read('src/trading_ai/execution_workspace/service.py')
    assert 'trade_plan_certification' in h
    assert 'm75_2_trade_plan_certified' in h
    assert 'institutional_trade_plan_certified' in e

def test_stock_scanner_shows_reference_and_certification():
    s=read('ui/workstation/src/StockIntelligenceScannerPage.tsx')
    assert 'Underlying reference' in s
    assert 'Reference as of' in s
    assert 'Trade plan certification' in s
    assert 'Certification failures' in s

def test_trade_builder_and_execution_workspace_show_certification():
    tb=read('ui/workstation/src/AdvancedTradeBuilderPage.tsx')
    ew=read('ui/workstation/src/ExecutionWorkspacePage.tsx')
    assert 'Institutional trade plan certification' in tb
    assert 'Institutional trade plan certification' in ew
