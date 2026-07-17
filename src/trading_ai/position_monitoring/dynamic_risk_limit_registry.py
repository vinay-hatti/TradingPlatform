from __future__ import annotations
from datetime import datetime, timezone
from .dynamic_risk_limit_policy import DynamicRiskLimitPolicy
from .dynamic_risk_limit_profile import DynamicRiskLimitProfile, ResolvedRiskLimit

def _parse(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class DynamicRiskLimitRegistry:
    def __init__(self, profiles: tuple[DynamicRiskLimitProfile, ...], policy: DynamicRiskLimitPolicy | None=None) -> None:
        self.policy=policy or DynamicRiskLimitPolicy(); self.policy.validate()
        if len(profiles)>self.policy.maximum_limit_profiles:
            raise ValueError('maximum_limit_profiles exceeded')
        self.profiles=profiles

    def resolve(self, *, metric: str, scopes: tuple[tuple[str,str], ...], as_of: datetime | None=None) -> ResolvedRiskLimit | None:
        now=as_of or datetime.now(timezone.utc)
        candidates=[]
        scope_set={(a.upper(),b.upper()) for a,b in scopes}
        for p in self.profiles:
            if not p.active or p.metric.upper()!=metric.upper(): continue
            if (p.scope_type.upper(),p.scope_value.upper()) not in scope_set: continue
            if _parse(p.effective_from)>now: continue
            if p.effective_to and _parse(p.effective_to)<=now: continue
            candidates.append(p)
        if not candidates: return None
        selected=max(candidates, key=lambda p:(p.precedence,p.version,p.effective_from))
        return ResolvedRiskLimit(metric=selected.metric,scope_type=selected.scope_type,scope_value=selected.scope_value,profile_id=selected.profile_id,warning_limit=selected.warning_limit,severe_limit=selected.severe_limit,critical_limit=selected.critical_limit,direction=selected.direction,precedence=selected.precedence,metadata=dict(selected.metadata))
