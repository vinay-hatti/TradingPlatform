from dataclasses import dataclass
import tempfile
from pathlib import Path
from trading_ai.paper_trading.paper_automation_orchestrator import PaperAutomationOrchestrator
from trading_ai.paper_trading.paper_automation_repository import JsonPaperAutomationRepository
@dataclass
class Obj: execution_key:str='e'; record:object=None
class Scan:
 def run(self,**k):
  d=type('D',(),{'aggregate_id':'a','command':type('C',(),{})()})();c=type('C',(),{'candidate_id':'c'})()
  return type('R',(),{'cycle_id':'cy','candidates':(c,), 'order_drafts':(d,)})()
class Exec:
 def execute(self,r): return Obj(r.execution_key,None)
class Pos:
 def process_execution(self,*a,**k): raise AssertionError

def main():
 with tempfile.TemporaryDirectory() as t:
  repo=JsonPaperAutomationRepository(Path(t)/'c.json');o=PaperAutomationOrchestrator(scan_service=Scan(),execution_service=Exec(),position_service=Pos(),checkpoint_repository=repo)
  r=o.run_cycle(session_id='s',candidates=(),institutional_decisions={},risk_gateway_decisions={},quotes={})
  assert r.allowed and r.checkpoint.state=='COMPLETED' and r.checkpoint.completed_stages==o.STAGES
  replay=o.recover(r.checkpoint.checkpoint_id,candidates=(),institutional_decisions={},risk_gateway_decisions={},quotes={})
  assert replay.recommendation=='IDEMPOTENT_REPLAY'
 print('All paper automation orchestration and restart-recovery assertions passed.')
if __name__=='__main__':main()
