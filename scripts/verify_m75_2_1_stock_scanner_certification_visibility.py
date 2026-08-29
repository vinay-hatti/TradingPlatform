from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
s=(root/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
checks={
 'trade_plan_column':'<th>Trade plan</th>' in s,
 'trade_plan_filter':"headerSelect('trade_plan', TRADE_PLAN_FILTER_VALUES)" in s,
 'certified_filter':"'CERTIFIED'" in s,
 'not_certified_filter':"'NOT_CERTIFIED'" in s,
 'not_evaluated_filter':"'NOT_EVALUATED'" in s,
 'failure_domain_filters':all(x in s for x in ["'FAILED_MARKET'","'FAILED_GEOMETRY'","'FAILED_STRATEGY'","'FAILED_RISK'","'FAILED_EXECUTION'","'FAILED_MANAGEMENT'","'FAILED_LIFECYCLE'"]),
 'persisted_certification': 'record.trade_plan_certification || null' in s,
 'persisted_status': 'record.trade_plan_certification_status || certification?.status' in s,
 'colspan_15':'colSpan={15}' in s,
}
for name,ok in checks.items():
 print(('PASS' if ok else 'FAIL'), name)
if not all(checks.values()): raise SystemExit(1)
print('M75.2.1 Stock Scanner certification visibility verification: PASSED')
