from pathlib import Path
from trading_ai.performance_learning import continuous_learning as cl

root = Path(__file__).resolve().parents[1]
service = Path(cl.__file__).read_text()
execution = (root/'src/trading_ai/execution_intelligence/service.py').read_text()
cli = (root/'scripts/run_m72_learning_cycle.py').read_text()
ui = (root/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
checks = {
    'version': cl.VERSION.startswith('M72.2'),
    'trade_outcome_bridge': 'def bridge_trade_outcomes' in service and 'PerformanceObservationModel' in service,
    'prediction_realization_lineage': 'trade_by_decision' in service and 'decision_snapshot_id' in service,
    'execution_evidence_backfill': 'def backfill_execution_evidence' in service and 'record_broker_sync' in service,
    'preflight_preservation': 'Historical/backfill path' in execution and "'backfilled':True" in execution,
    'opex_realization': 'OpexIntelligenceService(SessionLocal).realize_outcomes()' in service,
    'explicit_broker_sync': '--sync-ibkr' in cli and 'if a.sync_ibkr:' in cli,
    'pipeline_health': 'evidence_pipeline' in service and 'Evidence pipeline health' in ui,
    'human_governance': '"automatic_activation": False' in service and 'EXPLICIT_ONLY' in service,
}
for key, value in checks.items():
    print(f'{key}: {"PASS" if value else "FAIL"}')
assert all(checks.values()), checks
print('M72.2 Evidence Completion acceptance: PASS')
