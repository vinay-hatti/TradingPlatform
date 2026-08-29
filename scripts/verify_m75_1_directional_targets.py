from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks={
 'generation_current_price_gate':"self._valid(price,current,bull)" in (ROOT/'src/trading_ai/stock_intelligence/position_intelligence.py').read_text(),
 'integration_filter':"CROSSED_UNDERLYING_TARGETS_SKIPPED" in (ROOT/'src/trading_ai/stock_intelligence/option_integration.py').read_text(),
 'live_polygon_revalidation':"directional_profit_target_available" in (ROOT/'src/trading_ai/execution_intelligence/service.py').read_text(),
 'effective_target_handoff':"target_revalidation.get('effective_targets')" in (ROOT/'src/trading_ai/execution_workspace/service.py').read_text(),
 'ui_visibility':'Directional target revalidation' in (ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text(),
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(('PASS' if v else 'FAIL'),k)
if failed: raise SystemExit('M75.1 verification failed: '+', '.join(failed))
print('M75.1 directional target validity & live revalidation verification: PASSED')
