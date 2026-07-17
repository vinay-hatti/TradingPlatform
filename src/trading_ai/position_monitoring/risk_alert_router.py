from __future__ import annotations
import uuid
from .dynamic_risk_limit_profile import RiskAlertProfile, RiskBreachProfile

class RiskAlertRouter:
    CHANNELS={'WARNING':(('LOG','risk-monitoring'),),'SEVERE':(('LOG','risk-monitoring'),('EMAIL','risk-operations')),'CRITICAL':(('LOG','risk-monitoring'),('EMAIL','risk-leadership'),('PAGER','on-call-risk'))}
    def route(self, breach: RiskBreachProfile) -> tuple[RiskAlertProfile,...]:
        result=[]
        for channel,destination in self.CHANNELS[breach.severity]:
            result.append(RiskAlertProfile(alert_id=f'alert-{uuid.uuid4().hex}',breach_id=breach.breach_id,account_id=breach.account_id,severity=breach.severity,channel=channel,destination=destination,subject=f'{breach.severity} risk breach: {breach.metric}',message=f'{breach.metric}={breach.observed_value} breached {breach.limit_value} for {breach.scope_type}:{breach.scope_value}',metadata={'snapshot_id':breach.snapshot_id}))
        return tuple(result)
