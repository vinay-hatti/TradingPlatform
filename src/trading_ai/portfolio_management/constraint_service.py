from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Any
from .construction_profile import PortfolioConstructionPolicyProfile

def _f(v,d=0.0):
    try:return float(v if v is not None else d)
    except (TypeError,ValueError):return d

@dataclass(frozen=True)
class ConstraintValidationResult:
    valid: bool
    violations: tuple[dict[str,Any],...]
    warnings: tuple[str,...]
    projected_exposure: dict[str,Any]
    def to_dict(self): return asdict(self)

class PortfolioConstraintValidationService:
    def __init__(self, profile: PortfolioConstructionPolicyProfile|None=None): self.profile=profile or PortfolioConstructionPolicyProfile()
    def validate(self, proposed:list[dict[str,Any]], registry:dict[str,Any]) -> ConstraintValidationResult:
        open_existing=[x for x in registry.get('positions',[]) if str(x.get('status','OPEN')).upper()=='OPEN']
        rows=open_existing+proposed
        nlv=_f(registry.get('net_liquidation_value',100000),100000)
        dims={'symbol':'maximum_symbol_exposure_pct','sector':'maximum_sector_exposure_pct','strategy':'maximum_strategy_exposure_pct','direction':'maximum_direction_exposure_pct','correlation_group':'maximum_correlation_group_exposure_pct'}
        violations=[]; exposure={}; total=sum(_f(x.get('capital_committed',x.get('recommended_allocation',x.get('capital_required')))) for x in rows)
        if total>nlv*self.profile.maximum_portfolio_exposure_pct+1e-9: violations.append({'code':'PORTFOLIO_EXPOSURE_LIMIT_EXCEEDED','actual':total,'limit':nlv*self.profile.maximum_portfolio_exposure_pct})
        for field,limit_name in dims.items():
            agg=defaultdict(float)
            for x in rows: agg[str(x.get(field,'UNKNOWN')).upper()]+= _f(x.get('capital_committed',x.get('recommended_allocation',x.get('capital_required'))))
            exposure[field]=dict(agg); limit=nlv*getattr(self.profile,limit_name)
            for key,val in agg.items():
                if key and val>limit+1e-9: violations.append({'code':f'{field.upper()}_EXPOSURE_LIMIT_EXCEEDED','key':key,'actual':round(val,2),'limit':round(limit,2)})
        greek_totals={k:sum(_f(x.get(k, x.get('greeks',{}).get(k))) for x in rows) for k in ('delta','gamma','theta','vega','rho')}
        for k in ('delta','gamma','theta','vega','rho'):
            limit=getattr(self.profile,f'maximum_absolute_{k}')
            if abs(greek_totals[k])>limit: violations.append({'code':f'{k.upper()}_LIMIT_EXCEEDED','actual':greek_totals[k],'limit':limit})
        exposure.update({'total_capital':round(total,2),'greeks':greek_totals})
        warnings=[]
        if len(rows)==1: warnings.append('SINGLE_POSITION_PORTFOLIO')
        return ConstraintValidationResult(not violations,tuple(violations),tuple(warnings),exposure)
