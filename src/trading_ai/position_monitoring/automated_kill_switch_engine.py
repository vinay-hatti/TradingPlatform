from __future__ import annotations
from .continuous_monitoring_policy import ContinuousMonitoringPolicy
from .continuous_monitoring_profile import KillSwitchActivationDecision

class AutomatedKillSwitchEngine:
    def __init__(self, *, trading_control_service, policy: ContinuousMonitoringPolicy|None=None) -> None:
        self.service=trading_control_service; self.policy=policy or ContinuousMonitoringPolicy(); self.policy.validate()
    @staticmethod
    def _value(obj,name,default=None):
        if obj is None:return default
        if isinstance(obj,dict):return obj.get(name,default)
        return getattr(obj,name,default)
    def evaluate(self, *, account_id: str, breach_decision=None, reconciliation_decision=None, monitoring_failed: bool=False) -> KillSwitchActivationDecision:
        breaches=self._value(breach_decision,'breaches',()) or ()
        critical=tuple(self._value(b,'breach_id') for b in breaches if self._value(b,'severity')=='CRITICAL')
        reconciliation_failed=bool(reconciliation_decision is not None and not self._value(reconciliation_decision,'allowed',False))
        reasons=[]
        if critical and self.policy.activate_kill_switch_on_critical_breach: reasons.append('CRITICAL_RISK_BREACH')
        if reconciliation_failed and self.policy.activate_kill_switch_on_reconciliation_failure: reasons.append('BROKER_POSITION_RECONCILIATION_FAILURE')
        if monitoring_failed and self.policy.activate_kill_switch_on_monitoring_failure: reasons.append('CONTINUOUS_MONITORING_FAILURE')
        if not reasons: return KillSwitchActivationDecision(True,False,account_id,None,'continuous-monitoring',critical,reconciliation_failed,monitoring_failed,self.service.state(account_id))
        reason='|'.join(reasons)
        state=self.service.set_automatic_kill_switch(account_id=account_id,active=True,reason=reason)
        if self.policy.add_account_halt_on_kill_switch and not any(h.active and h.scope_type=='ACCOUNT' and h.scope_value==account_id.upper() for h in state.halts):
            state=self.service.add_halt(account_id=account_id,scope_type='ACCOUNT',scope_value=account_id,reason=reason,source='continuous-monitoring',reduce_only=self.policy.allow_reduce_only_after_activation)
        return KillSwitchActivationDecision(True,True,account_id,reason,'continuous-monitoring',critical,reconciliation_failed,monitoring_failed,state,{'reduce_only':self.policy.allow_reduce_only_after_activation})
