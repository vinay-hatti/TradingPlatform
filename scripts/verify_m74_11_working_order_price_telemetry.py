from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
svc=(root/'src/trading_ai/execution_intelligence/service.py').read_text()
ws=(root/'src/trading_ai/execution_workspace/service.py').read_text()
router=(root/'src/trading_ai/execution_intelligence/router.py').read_text()
ui=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
api=(root/'ui/workstation/src/api.ts').read_text()
assert 'def working_telemetry(self,intent_id)' in svc
assert "'frozen_boundary_price':boundary" in svc
assert "'envelope_consumed_pct':round(progress,4)" in svc
assert "'phase':phase,'phase_reason':phase_reason" in svc
assert 'working-telemetry' in router and 'working-telemetry' in api
assert "'working_order_telemetry':telemetry" in ws
assert 'Current working limit' in ui and 'Approved reference' in ui and 'Envelope consumed' in ui
assert 'Room to boundary' in ui and 'Frozen approval boundary reached' in ui
assert 'setInterval(poll,5000)' in ui
print('M74.11 working-order price telemetry and envelope visibility verification: PASSED')
