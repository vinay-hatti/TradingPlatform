from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import uuid
from .continuous_monitoring_policy import ContinuousMonitoringPolicy
from .continuous_monitoring_profile import ContinuousMonitoringCycleState, ContinuousMonitoringDecision

class ContinuousMonitoringOrchestrator:
    def __init__(self, *, position_service, greeks_service, dynamic_limit_service, reconciliation_engine, kill_switch_engine, repository, policy: ContinuousMonitoringPolicy|None=None) -> None:
        self.position_service=position_service;self.greeks_service=greeks_service;self.dynamic_limit_service=dynamic_limit_service;self.reconciliation_engine=reconciliation_engine;self.kill_switch_engine=kill_switch_engine;self.repository=repository;self.policy=policy or ContinuousMonitoringPolicy();self.policy.validate()
    def run_cycle(self, *, account_id: str, position_kwargs: dict, greeks_kwargs: dict, broker_positions: tuple, platform_positions: tuple) -> ContinuousMonitoringDecision:
        previous=self.repository.latest_for_account(account_id);sequence=(previous.sequence_number+1) if previous else 1;cycle_id=f'monitor-{uuid.uuid4().hex}'
        state=ContinuousMonitoringCycleState(cycle_id,account_id,sequence,'RUNNING');self.repository.save(state)
        stages=[]
        try:
            p=self.position_service.evaluate_and_publish(**position_kwargs);stages.append('POSITION_SNAPSHOT')
            if self.policy.require_position_snapshot and not p.allowed: raise RuntimeError('POSITION_SNAPSHOT_REJECTED')
            g=self.greeks_service.evaluate_and_publish(**greeks_kwargs);stages.append('GREEKS_MONITORING')
            if self.policy.require_greeks_snapshot_for_options and not g.allowed: raise RuntimeError('GREEKS_MONITORING_REJECTED')
            b=self.dynamic_limit_service.evaluate_monitoring_states(position_state=p.risk_state,greeks_state=g.risk_state);stages.append('DYNAMIC_LIMITS')
            r=self.reconciliation_engine.evaluate(account_id=account_id,broker_positions=broker_positions,platform_positions=platform_positions);stages.append('BROKER_RECONCILIATION')
            k=self.kill_switch_engine.evaluate(account_id=account_id,breach_decision=b,reconciliation_decision=r);stages.append('KILL_SWITCH_GOVERNANCE')
            allowed=bool(p.allowed and g.allowed and b.allowed and r.allowed and not k.activated)
            state=replace(state,state='COMPLETED',completed_stages=tuple(stages),position_snapshot_id=p.snapshot_id,greeks_snapshot_id=g.snapshot_id,breach_count=len(b.breaches),reconciliation_allowed=r.allowed,kill_switch_activated=k.activated,completed_at=datetime.now(timezone.utc).isoformat());self.repository.save(state)
            return ContinuousMonitoringDecision(True,allowed,account_id,cycle_id,'MONITOR' if allowed else 'HALT',p,g,b,r,k,state,rejection_reasons=tuple((*getattr(b,'rejection_reasons',()),*r.rejection_reasons)),metadata={'sequence_number':sequence})
        except Exception as exc:
            k=self.kill_switch_engine.evaluate(account_id=account_id,monitoring_failed=True)
            state=replace(state,state='FAILED',completed_stages=tuple(stages),failed_stage=(stages[-1] if stages else 'STARTUP'),error=str(exc),kill_switch_activated=k.activated,completed_at=datetime.now(timezone.utc).isoformat());self.repository.save(state)
            return ContinuousMonitoringDecision(True,False,account_id,cycle_id,'HALT',kill_switch_decision=k,cycle_state=state,rejection_reasons=(str(exc),),metadata={'sequence_number':sequence})
