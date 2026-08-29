from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
required=['src/trading_ai/trend_intelligence/operations_contracts.py','src/trading_ai/trend_intelligence/operations_policy.py','src/trading_ai/trend_intelligence/operations_engine.py','src/trading_ai/trend_intelligence/operations_service.py','src/trading_ai/trend_intelligence/operations_serialization.py','src/trading_ai/trend_intelligence/operations_reporting.py','scripts/run_trend_phase6_operations.py','scripts/test_m52_phase6_operations.py','scripts/test_m52_acceptance.py']
missing=[x for x in required if not (ROOT/x).exists()]
assert not missing,missing
print('All Milestone 52 Phase 6 package contract assertions passed.')
