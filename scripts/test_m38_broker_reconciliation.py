import json,tempfile
from pathlib import Path
from trading_ai.execution_orchestration.service import ExecutionOrchestrationService
with tempfile.TemporaryDirectory() as td:
 p=Path(td); handoff=p/'handoff.json'; risk=p/'risk.json'; broker=p/'broker.json'; out=p/'out'; svc=ExecutionOrchestrationService()
 handoff.write_text(json.dumps({'portfolio_id':'PRIMARY','orders':[{'client_order_id':'C1','symbol':'NVDA','strategy':'CALL','direction':'CALL','contracts':1,'capital_limit':300}]})); risk.write_text(json.dumps({'trading_control':'ALLOW','allow_new_risk':True})); svc.run(handoff,risk,out)
 broker.write_text(json.dumps({'orders':[{'client_order_id':'C1','broker_order_id':'B1','status':'FILLED','filled_quantity':1,'average_fill_price':2.5,'updated_at':'2026-07-22T00:00:00Z'}]}))
 result=svc.reconcile_broker_state(out/'execution_queue.json',out/'execution_events.json',broker); assert result['changed']==1
 q=json.loads((out/'execution_queue.json').read_text()); assert q['orders'][0]['status']=='FILLED' and q['orders'][0]['average_fill_price']==2.5
print('Milestone 38 broker reconciliation assertions passed.')
