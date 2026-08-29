import json,tempfile
from pathlib import Path
from trading_ai.execution_orchestration.service import ExecutionOrchestrationService
with tempfile.TemporaryDirectory() as td:
 p=Path(td); handoff=p/'handoff.json'; risk=p/'risk.json'; out=p/'out'
 handoff.write_text(json.dumps({'handoff_id':'H1','portfolio_id':'PRIMARY','orders':[{'client_order_id':'C1','symbol':'AAPL','strategy':'BULL_CALL_SPREAD','direction':'CALL','contracts':1,'capital_limit':500,'source_candidate_id':'X'}]}))
 risk.write_text(json.dumps({'assessment_id':'R1','trading_control':'BLOCK_NEW_RISK','allow_new_risk':False,'blocking_breach_ids':['B1']}))
 r=ExecutionOrchestrationService().run(handoff,risk,out)
 assert r.blocked_count==1 and r.status=='BLOCKED'
 q=json.loads((out/'execution_queue.json').read_text()); assert q['orders'][0]['status']=='RISK_BLOCKED'
print('Milestone 38 risk-gating assertions passed.')
