from pathlib import Path
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager
from trading_ai.execution_intelligence.entry_chase import advance_coarse_tick,monotonic_broker_candidate
from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy

root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/execution_intelligence/service.py').read_text()
ws=(root/'src/trading_ai/execution_workspace/service.py').read_text()
transport=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
auto=(root/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()

checks={
 'version': AutomaticEntryFillManager.VERSION.startswith('M73.0.6-'),
 'max_reprice_rests': "RESTING_AT_FINAL_LIMIT" in svc and "reprice_count>=policy.maximum_reprices" in svc,
 'monotonic_chase': 'monotonic_broker_candidate' in svc and 'monotonic_broker_candidate' in ws,
 'tick_noop_not_counted': 'm70_noop_reprice_history' in ws and 'WAIT_TICK_UNCHANGED' in ws,
 'structured_cancel_reasons': all(x in svc for x in ['EDGE_LOST','ORDER_AGE_EXCEEDED','APPROVAL_ENVELOPE_OR_RISK_BREACH']),
 'modify_spacing': 'minimum_modify_interval_seconds' in svc,
 'duplicate_id_fail_closed': 'BROKER_MODIFY_SYNC_ERROR' in ws and 'prepare_existing_order_for_modify' in transport,
 'max_age_cancels_broker': 'cancel_required' in ws and "truth.get('cancel_required')" in auto,
 'actual_modify_only_counts': "'broker_modified':True" in ws and "m70_reprice_count" in ws,
}
for k,v in checks.items():
 print(f"{k}: {'PASS' if v else 'FAIL'}")
 assert v,k
assert monotonic_broker_candidate('BUY',7.64,7.60)==7.64
assert monotonic_broker_candidate('SELL',2.25,2.30)==2.25
assert advance_coarse_tick(side='BUY',current_price=.8,theoretical_price=.8237,normalized_price=.8,increment=.05,maximum_debit=.9,executable_price=.85)['price']==.8
assert advance_coarse_tick(side='BUY',current_price=.8,theoretical_price=.835,normalized_price=.8,increment=.05,maximum_debit=.9,executable_price=.85)['price']==.85
p=load_execution_intelligence_policy();assert p.minimum_modify_interval_seconds>=0
print('M73.0.6 Entry Chase State-Machine verifier: PASS')
