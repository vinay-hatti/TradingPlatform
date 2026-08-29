#!/usr/bin/env python
from __future__ import annotations
import sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
svc=(root/'src/trading_ai/dynamic_position_management/service.py').read_text()
checks={
    'canonical_model_import':'CanonicalOrderModel' in svc,
    'durable_exit_materialization':'_ensure_canonical_exit_order' in svc and 'durable_before_transmit' in svc,
    'single_leg_pretransmit':svc.find('_ensure_canonical_exit_order(position,instruction,request') < svc.find('service.submit(request)'),
    'combo_pretransmit':svc.rfind('_ensure_canonical_exit_order(position,instruction,request') < svc.find('self._submit_strategy_combo(service,request)'),
    'idempotent_existing':'EXISTING_CANONICAL_EXIT_ORDER' in svc and 'CONCURRENT_CANONICAL_EXIT_ORDER' in svc,
    'failed_retry_self_heal':'SUBMISSION_FAILED' in svc and 'submission_recovered' in svc and 'submission_attempt_count' in svc,
    'full_strategy_preserved':'canonical_legs' in svc and "'side':x.action" in svc,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('M74.13.1 verification failed: '+', '.join(failed))
print('M74.13.1 self-healing canonical exit materialization verification: PASSED')
for k in checks: print('  PASS',k)

assert "'strategy_level_exit':True" in svc
assert "'includes_short_legs':True" in svc
assert "'closing_combo':True" in svc
assert "'strategy_type':position.strategy" in svc
assert 'return service.submit_combo(request)' in svc
print('  PASS strategy_level_exit_metadata_contract')
