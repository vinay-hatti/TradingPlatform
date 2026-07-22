import json,tempfile
from pathlib import Path
from trading_ai.execution_orchestration.reporting_service import ExecutionOrchestrationReportingService
with tempfile.TemporaryDirectory() as td:
 p=Path(td); (p/'execution_queue.json').write_text(json.dumps({'orders':[{'status':'FILLED'}]})); (p/'execution_events.json').write_text(json.dumps({'events':[{}]})); (p/'workflow_result.json').write_text(json.dumps({'status':'READY','trading_control':'ALLOW'}))
 r=ExecutionOrchestrationReportingService().generate(p); assert r['order_count']==1 and (p/'milestone38_closure.html').exists()
print('Milestone 38 reporting assertions passed.')
