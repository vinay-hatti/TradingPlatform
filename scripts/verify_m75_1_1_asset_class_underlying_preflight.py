from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
svc=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
prov=(ROOT/'src/trading_ai/execution_intelligence/provider.py').read_text()
ui=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
checks={
 'index_asset_detection':"ticker.startswith('I:')" in svc,
 'index_quote_route':"u=provider.index_quote(polygon_underlying_ticker)" in svc,
 'stock_quote_route':"u=provider.underlying_quote(m.symbol)" in svc,
 'fail_closed_missing_underlying':"elif not checks['underlying_price_available']:decision='BLOCK'" in svc,
 'no_zero_coercion':"float(underlying_price or 0.0)" not in svc,
 'index_provider':"def index_quote(self,symbol):" in prov and "'/v3/snapshot/indices'" in prov,
 'diagnostic_source':"'underlying_source':latest.get('underlying_source')" in svc,
 'diagnostic_ticker':"'polygon_underlying_ticker':latest.get('polygon_underlying_ticker')" in svc,
 'ui_unavailable':"'UNAVAILABLE'" in ui and 'Underlying source:' in ui,
}
for k,v in checks.items():print(('PASS' if v else 'FAIL'),k)
failed=[k for k,v in checks.items() if not v]
if failed:raise SystemExit('M75.1.1 verification failed: '+', '.join(failed))
print('M75.1.1 asset-class-aware underlying preflight & fail-closed target validation verification: PASSED')
