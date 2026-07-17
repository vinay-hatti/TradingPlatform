from __future__ import annotations
from datetime import datetime, timezone
import uuid
from .dynamic_risk_limit_policy import DynamicRiskLimitPolicy
from .dynamic_risk_limit_profile import RiskBreachProfile, RiskEscalationProfile

def _parse(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class RiskEscalationEngine:
    def __init__(self,policy: DynamicRiskLimitPolicy|None=None): self.policy=policy or DynamicRiskLimitPolicy(); self.policy.validate()
    def evaluate(self,breach: RiskBreachProfile, *, as_of: datetime|None=None):
        if breach.status=='RESOLVED' or breach.severity=='WARNING': return ()
        now=as_of or datetime.now(timezone.utc); age=(now-_parse(breach.first_detected_at)).total_seconds(); threshold=self.policy.critical_escalation_after_seconds if breach.severity=='CRITICAL' else self.policy.severe_escalation_after_seconds
        if age<threshold: return ()
        level=min(self.policy.maximum_escalation_level, breach.escalation_level+1)
        role={1:'RISK_MANAGER',2:'HEAD_OF_TRADING',3:'EXECUTIVE_ON_CALL'}.get(level,'EXECUTIVE_ON_CALL')
        return (RiskEscalationProfile(escalation_id=f'escalation-{uuid.uuid4().hex}',breach_id=breach.breach_id,level=level,reason=f'{breach.severity}_BREACH_UNRESOLVED',target_role=role),)
