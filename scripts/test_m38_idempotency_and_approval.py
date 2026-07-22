import json,tempfile
from pathlib import Path
from trading_ai.execution_orchestration.service import ExecutionOrchestrationService
with tempfile.TemporaryDirectory() as td:
 p=Path(td); handoff=p/'handoff.json'; risk=p/'risk.json'; out=p/'out'; svc=ExecutionOrchestrationService()
 handoff.write_text(json.dumps({'handoff_id':'H1','portfolio_id':'PRIMARY','orders':[{'client_order_id':'C1','symbol':'MSFT','strategy':'BULL_PUT_SPREAD','direction':'PUT','contracts':2,'capital_limit':900}]}))
 risk.write_text(json.dumps({'assessment_id':'R1','trading_control':'ALLOW','allow_new_risk':True}))
 svc.run(handoff,risk,out); svc.run(handoff,risk,out)
 q=json.loads((out/'execution_queue.json').read_text()); assert len(q['orders'])==1
 oid=q['orders'][0]['execution_order_id']; approved=svc.approve(out/'execution_queue.json',out/'execution_events.json',oid,'tester')
 assert approved['status']=='RELEASED_TO_BROKER'
print('Milestone 38 idempotency and approval assertions passed.')
