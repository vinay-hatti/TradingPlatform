from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from .dynamic_risk_limit_profile import ResolvedRiskLimit, RiskBreachProfile

def _breached(value: float, limit: float, direction: str) -> bool:
    d=direction.upper()
    if d=='MAX': return value>limit
    if d=='MIN': return value<limit
    if d=='ABSOLUTE_MAX': return abs(value)>limit
    raise ValueError(f'Unsupported direction: {direction}')

class RiskBreachEngine:
    @staticmethod
    def severity(value: float, limit: ResolvedRiskLimit) -> tuple[str,float] | None:
        for name, threshold in (('CRITICAL',limit.critical_limit),('SEVERE',limit.severe_limit),('WARNING',limit.warning_limit)):
            if threshold is not None and _breached(value,float(threshold),limit.direction):
                return name,float(threshold)
        return None

    def detect(self, *, account_id: str, snapshot_id: str, metric: str, scope_type: str, scope_value: str, observed_value: float, limit: ResolvedRiskLimit, detected_at: datetime | None=None) -> RiskBreachProfile | None:
        result=self.severity(observed_value,limit)
        if result is None: return None
        severity, threshold=result
        stamp=(detected_at or datetime.now(timezone.utc)).isoformat()
        raw=f'{account_id}|{metric}|{scope_type}|{scope_value}|{limit.profile_id}'
        breach_id='breach-'+hashlib.sha256(raw.encode()).hexdigest()[:24]
        return RiskBreachProfile(breach_id=breach_id,account_id=account_id,snapshot_id=snapshot_id,metric=metric,scope_type=scope_type,scope_value=scope_value,observed_value=float(observed_value),limit_value=threshold,severity=severity,direction=limit.direction,first_detected_at=stamp,last_detected_at=stamp,metadata={'limit_profile_id':limit.profile_id,'precedence':limit.precedence})
