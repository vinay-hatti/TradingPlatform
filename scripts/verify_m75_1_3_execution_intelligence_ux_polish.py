from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ui=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
checks={
 'label_value_skipped_rows': all(x in ui for x in ('Skipped targets','Current underlying:','Exceeded by','Undercut by','<b>{distanceLabel}:</b>')),
 'skipped_percent_context': 'Math.abs(Number(x.distance)/Number(x.target_value))*100' in ui and 'pct.toFixed(2)' in ui,
 'split_market_freshness_rows': all(x in ui for x in ('<b>Underlying quote age:</b>','<b>Option quote age:</b>')),
 'effective_target_renumbering': '<b>Target {i+1}:</b>' in ui,
 'active_target_progress': all(x in ui for x in ('Current objective:','Distance remaining:')),
 'no_target_rebuild_explanation': all(x in ui for x in ('No executable profit targets remain.','Rebuild trade plan.')),
 'operator_sections': all(x in ui for x in ('Execution validation','Market data','Directional target validation')),
}
for k,v in checks.items(): print(('PASS' if v else 'FAIL'),k)
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('M75.1.3 verification failed: '+', '.join(failed))
print('M75.1.3 execution intelligence UX polish verification: PASSED')
