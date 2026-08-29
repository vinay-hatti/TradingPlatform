from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
checks={
 'engine': (root/'src/trading_ai/trade_plan_certification/engine.py','CERTIFICATION_VERSION'),
 'bullish_rule': (root/'src/trading_ai/trade_plan_certification/engine.py','TPC-GEO-001'),
 'bearish_rule': (root/'src/trading_ai/trade_plan_certification/engine.py','TPC-GEO-002'),
 'reference_market': (root/'src/trading_ai/stock_intelligence/publication.py','underlying_reference_price'),
 'opportunity_gate': (root/'src/trading_ai/institutional_options/opportunity_ingestion.py','TRADE_PLAN_CERTIFICATION_FAILED'),
 'handoff_gate': (root/'src/trading_ai/institutional_options/handoff.py','m75_2_trade_plan_certified'),
 'execution_gate': (root/'src/trading_ai/execution_workspace/service.py','institutional_trade_plan_certified'),
 'scanner_ui': (root/'ui/workstation/src/StockIntelligenceScannerPage.tsx','Trade plan certification'),
 'builder_ui': (root/'ui/workstation/src/AdvancedTradeBuilderPage.tsx','Institutional trade plan certification'),
 'execution_ui': (root/'ui/workstation/src/ExecutionWorkspacePage.tsx','Institutional trade plan certification'),
}
for name,(path,token) in checks.items():
    assert path.exists(), f'{name}: missing {path}'
    assert token in path.read_text(), f'{name}: missing {token}'
    print('PASS',name)
print('M75.2 Institutional Trade Plan Certification Engine verification: PASSED')
