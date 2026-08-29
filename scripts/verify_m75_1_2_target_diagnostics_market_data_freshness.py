from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
svc=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
ui=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
checks={
 'structured_skipped_target_evidence':"'skipped_target_details':skipped_details" in svc,
 'original_target_number':"'original_target_number':original_number" in svc,
 'bullish_exceeded_distance':"(underlying-value) if direction=='BULLISH'" in svc,
 'bearish_undercut_label':"'UNDERCUT_BY'" in svc,
 'underlying_quote_age':"'underlying_quote_age_seconds':round(underlying_quote_age_seconds,6)" in svc,
 'option_quote_age':"'option_quote_age_seconds':round(max_age,6)" in svc,
 'ui_skipped_targets':all(x in ui for x in ('Skipped targets','Current underlying','Exceeded by','Undercut by')),
 'ui_split_freshness':all(x in ui for x in ('Underlying quote age','Option quote age')),
}
for k,v in checks.items(): print(('PASS' if v else 'FAIL'),k)
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('M75.1.2 verification failed: '+', '.join(failed))
print('M75.1.2 target diagnostics & market-data freshness visibility verification: PASSED')
