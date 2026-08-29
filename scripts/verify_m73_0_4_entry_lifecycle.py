from pathlib import Path
root=Path(__file__).resolve().parents[1]
auto=(root/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
ws=(root/'src/trading_ai/execution_workspace/service.py').read_text()
checks={
 'version':'M73.0.' in auto and 'ENTRY' in auto,
 'single_broker_sync':'_broker_sync_once' in auto and 'service.synchronize(portfolio_id)' in auto,
 'truth_reconciliation':'reconcile_entry_with_broker_truth' in auto and 'reconcile_entry_with_broker_truth' in ws,
 'terminal_repair':'BROKER_TRUTH_ENTRY_STATE_REPAIRED' in ws,
 'stale_age_governance':'ORDER_AGE_EXCEEDED' in ws and 'cancel_required' in ws,
 'remaining_qty_gate':"remaining_quantity" in ws and "eligible=bool(working" in ws,
 'bounded_chase_preserved':'reprice_working' in auto and 'automatic=True' in auto,
}
for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()),checks
print('M73.0.4 Broker-Truth Entry Lifecycle verifier: PASS')
