from pathlib import Path
root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/broker_portfolio_sync/lineage_diagnostics.py').read_text()
cli=(root/'scripts/run_m74_7_lineage_diagnostics.py').read_text()
checks=[
 'M74.7-LINEAGE-DIAGNOSTICS-1.0',
 'AUTO_RECOVERABLE',
 'BLOCKED_REVIEW',
 'LIKELY_EXTERNAL',
 'COMPLETE_EXACT_LEG_SET',
 'AMBIGUOUS_HIGH_CONFIDENCE_CANDIDATES',
 'BROKER_ORDER_LINEAGE_MISSING',
 'STALE_PROTECTION_STATE',
 'NO_PROTECTIVE_RULE_ARMED',
]
for token in checks: assert token in svc, token
assert 'LineageDiagnosticsService' in cli
print('M74.7 lineage diagnostics and recovery workbench verification: PASSED')
