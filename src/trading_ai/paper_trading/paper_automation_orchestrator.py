from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import uuid
from .paper_automation_profile import PaperAutomationCheckpoint, PaperAutomationCycleResult
from .paper_execution_profile import PaperExecutionRequest

class PaperAutomationOrchestrator:
    STAGES=('SCAN_DECISION','PAPER_EXECUTION','POSITION_PROCESSING','COMPLETE')
    def __init__(self,*,scan_service,execution_service,position_service,checkpoint_repository):
        self.scan_service=scan_service;self.execution_service=execution_service;self.position_service=position_service;self.checkpoints=checkpoint_repository
    def _save(self,c,stage,**kw):
        done=tuple(dict.fromkeys((*c.completed_stages,stage)))
        pending=tuple(x for x in self.STAGES if x not in done)
        u=replace(c,stage=stage,completed_stages=done,pending_stages=pending,state='COMPLETED' if not pending else 'IN_PROGRESS',updated_at=datetime.now(timezone.utc).isoformat(),**kw)
        return self.checkpoints.save(u)
    def run_cycle(self,*,session_id,candidates,institutional_decisions,risk_gateway_decisions,quotes,asset_metadata=None):
        cp=PaperAutomationCheckpoint(checkpoint_id='paper-auto-'+uuid.uuid4().hex,session_id=session_id,cycle_id='PENDING',stage='START',pending_stages=self.STAGES)
        self.checkpoints.save(cp)
        try:
            scan=self.scan_service.run(session_id=session_id,candidates=candidates,institutional_decisions=institutional_decisions,risk_gateway_decisions=risk_gateway_decisions)
            cp=replace(cp,cycle_id=scan.cycle_id,candidate_ids=tuple(c.candidate_id for c in scan.candidates),order_draft_ids=tuple(d.aggregate_id for d in scan.order_drafts)); self.checkpoints.save(cp)
            cp=self._save(cp,'SCAN_DECISION')
            execs=[]
            for draft in scan.order_drafts:
                key=f'paper-exec-{scan.cycle_id}-{draft.aggregate_id}'
                req=PaperExecutionRequest(execution_key=key,session_id=session_id,cycle_id=scan.cycle_id,order_draft=draft,quotes=quotes)
                execs.append(self.execution_service.execute(req))
            cp=self._save(cp,'PAPER_EXECUTION',execution_keys=tuple(e.execution_key for e in execs))
            positions=[]; meta=asset_metadata or {}
            for e in execs:
                if e.record and e.record.fills:
                    m=meta.get(e.record.fills[0].symbol,{})
                    positions.append(self.position_service.process_execution(e.record,asset_class=m.get('asset_class','OPTION'),multiplier=int(m.get('multiplier',100))))
            cp=self._save(cp,'POSITION_PROCESSING',position_ids=tuple(p.position.position_id for p in positions if p.position))
            cp=self._save(cp,'COMPLETE')
            return PaperAutomationCycleResult(True,True,session_id,scan.cycle_id,'COMPLETED',scan,tuple(execs),tuple(positions),cp)
        except Exception as exc:
            cp=replace(cp,state='FAILED',retry_count=cp.retry_count+1,last_error=str(exc),updated_at=datetime.now(timezone.utc).isoformat());self.checkpoints.save(cp)
            return PaperAutomationCycleResult(True,False,session_id,None,'RECOVER',checkpoint=cp,errors=(str(exc),))
    def recover(self,checkpoint_id,**kwargs):
        cp=self.checkpoints.get(checkpoint_id)
        if cp is None: raise KeyError(checkpoint_id)
        if cp.state=='COMPLETED': return PaperAutomationCycleResult(True,True,cp.session_id,cp.cycle_id,'IDEMPOTENT_REPLAY',checkpoint=cp,warnings=('CHECKPOINT_ALREADY_COMPLETED',))
        result=self.run_cycle(session_id=cp.session_id,**kwargs)
        return replace(result,warnings=(*result.warnings,'RECOVERY_REPLAY'))
