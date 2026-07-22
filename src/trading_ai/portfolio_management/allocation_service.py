from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .allocation_profile import CapitalAllocationProfile


def _f(v: Any, d: float=0.0) -> float:
    try: return float(v if v is not None else d)
    except (TypeError, ValueError): return d

@dataclass(frozen=True)
class AllocationResult:
    status: str
    net_liquidation_value: float
    cash_balance: float
    reserve_required: float
    deployable_cash: float
    deployment_limit: float
    allocated_capital: float
    unallocated_capital: float
    allocations: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    policy: dict[str, Any]
    def to_dict(self): return asdict(self)

class PortfolioAwareCapitalAllocationService:
    def __init__(self, profile: CapitalAllocationProfile|None=None):
        self.profile=profile or CapitalAllocationProfile()
    def allocate(self, positions: list[dict[str,Any]], registry: dict[str,Any]) -> AllocationResult:
        nlv=_f(registry.get('net_liquidation_value', registry.get('account',{}).get('initial_capital',100000)),100000)
        cash=_f(registry.get('cash_balance',nlv),nlv)
        committed=sum(_f(x.get('capital_committed')) for x in registry.get('positions',[]) if str(x.get('status','OPEN')).upper()=='OPEN')
        reserve=max(nlv*self.profile.reserve_cash_pct,self.profile.minimum_reserve_dollars)
        deployable=max(cash-reserve,0.0)
        deployment_limit=max(nlv*self.profile.maximum_deployment_pct-committed,0.0)
        budget=min(deployable,deployment_limit)
        scored=[]
        for p in positions:
            score=max(_f(p.get('ranking_score')),0)/100
            ret=max(_f(p.get('expected_return_pct')),0)/100
            fit=max(_f(p.get('portfolio_fit_score')),0)/100
            div=1.0 if str(p.get('sector','UNKNOWN')).upper()!='UNKNOWN' else .5
            merit=score*self.profile.score_weight+ret*self.profile.return_weight+fit*self.profile.fit_weight+div*self.profile.diversification_weight
            scored.append((max(merit,0.0001),p))
        total=sum(x[0] for x in scored) or 1.0
        allocations=[]; used=0.0
        cap=nlv*self.profile.maximum_allocation_per_candidate_pct
        for merit,p in sorted(scored,key=lambda x:x[0],reverse=True):
            requested=max(_f(p.get('capital_required')),self.profile.minimum_allocation_dollars)
            target=min(budget*merit/total,requested,cap,max(budget-used,0))
            if target<self.profile.minimum_allocation_dollars: continue
            q=dict(p); q['recommended_allocation']=round(target,2); q['allocation_merit']=round(merit,6)
            q['allocation_pct_nlv']=round(target/nlv*100,4) if nlv else 0.0
            allocations.append(q); used+=target
        warnings=[]
        if budget<=0: warnings.append('NO_DEPLOYABLE_CAPITAL')
        if reserve>cash: warnings.append('CASH_BELOW_REQUIRED_RESERVE')
        return AllocationResult('COMPLETE' if allocations else 'REVIEW_REQUIRED',round(nlv,2),round(cash,2),round(reserve,2),round(deployable,2),round(deployment_limit,2),round(used,2),round(max(budget-used,0),2),tuple(allocations),tuple(warnings),self.profile.to_dict())
