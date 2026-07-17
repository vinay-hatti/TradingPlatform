from __future__ import annotations
from .continuous_monitoring_policy import ContinuousMonitoringPolicy
from .continuous_monitoring_profile import BrokerPositionDifference, BrokerPositionReconciliationDecision

class BrokerPositionReconciliationEngine:
    def __init__(self, policy: ContinuousMonitoringPolicy|None=None) -> None:
        self.policy=policy or ContinuousMonitoringPolicy(); self.policy.validate()
    @staticmethod
    def _grade(score: float):
        if score>=95:return 'A','LOW'
        if score>=85:return 'B','MODERATE'
        if score>=70:return 'C','SEVERE'
        return 'F','CRITICAL'
    @staticmethod
    def _value(obj,name,default=None):
        if isinstance(obj,dict): return obj.get(name,default)
        return getattr(obj,name,default)
    def evaluate(self, *, account_id: str, broker_positions: tuple, platform_positions: tuple) -> BrokerPositionReconciliationDecision:
        broker={self._value(p,'symbol'):p for p in broker_positions if self._value(p,'account_id')==account_id}
        platform={self._value(p,'symbol'):p for p in platform_positions if self._value(p,'account_id')==account_id}
        differences=[];missing_broker=[];missing_platform=[]
        for symbol in sorted(set(broker)|set(platform)):
            bp=broker.get(symbol); pp=platform.get(symbol)
            if bp is None: missing_platform.append(symbol); continue
            if pp is None: missing_broker.append(symbol); continue
            bq=float(self._value(bp,'quantity',0)); pq=float(self._value(pp,'quantity',0))
            bc=float(self._value(bp,'average_cost',0)); pc=float(self._value(pp,'average_cost',0))
            qd=bq-pq; cd=bc-pc; pct=abs(cd)/abs(bc) if bc else (0.0 if pc==0 else None)
            matched=abs(qd)<=self.policy.reconciliation_quantity_tolerance and pct is not None and pct<=self.policy.reconciliation_cost_tolerance_pct
            differences.append(BrokerPositionDifference(symbol,bq,pq,qd,bc,pc,cd,pct,matched))
        failed=[d for d in differences if not d.matched]
        total=max(1,len(differences)+len(missing_broker)+len(missing_platform)); score=100*(total-len(failed)-len(missing_broker)-len(missing_platform))/total
        allowed=not failed and not missing_broker and not missing_platform
        grade,severity=self._grade(score)
        reasons=tuple([f'POSITION_MISMATCH:{d.symbol}' for d in failed]+[f'MISSING_AT_BROKER:{s}' for s in missing_broker]+[f'MISSING_AT_PLATFORM:{s}' for s in missing_platform])
        return BrokerPositionReconciliationDecision(True,allowed,account_id,round(score,2),grade,severity,'MATCHED' if allowed else 'RECONCILE',tuple(differences),tuple(missing_broker),tuple(missing_platform),reasons)
