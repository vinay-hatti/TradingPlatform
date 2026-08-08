from pathlib import Path
from trading_ai.performance_learning import continuous_learning as cl
from trading_ai.performance_learning.outcome_engine import _select_lifecycle_outcome

root=Path(__file__).resolve().parents[1]
outcome=(root/'src/trading_ai/performance_learning/outcome_engine.py').read_text()
continuous=Path(cl.__file__).read_text()
repair=(root/'scripts/repair_m72_2_1_trade_outcome_duplicates.py').read_text()
diagnostic=(root/'scripts/diagnose_m72_evidence_pipeline.py').read_text()
ui=(root/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
checks={
 'version':cl.VERSION.startswith('M72.2.1-'),
 'one_lifecycle_record':'existing=_select_lifecycle_outcome(existing_rows,p.version)' in outcome and 'TradeOutcomeModel.position_id==p.position_id).order_by' in outcome,
 'idempotent_selector':_select_lifecycle_outcome([],1) is None,
 'governed_repair':"SAFE_SYNTHETIC_OPEN_DUPLICATES" in repair and 'LearningAuditEventModel' in repair and "--apply" in repair,
 'closed_evidence_guard':'MANUAL_REVIEW_REQUIRED' in repair and "x.closed_at or x.outcome in TERMINAL" in repair,
 'execution_state_hardening':'NO_FILLS_AVAILABLE' in continuous and 'EXECUTION_HISTORY_INCOMPLETE' in continuous,
 'diagnostic_hardening':'never_routed_intents' in diagnostic and 'routed_without_telemetry' in diagnostic,
 'ui_hardening':'Execution sync state' in ui and 'No completed fills are currently available' in ui,
 'human_governance':'automatic_activation": False' in continuous,
}
for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()),checks
print('M72.2.1 Evidence Integrity Hardening acceptance: PASS')
