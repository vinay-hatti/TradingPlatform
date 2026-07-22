from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
from .allocation_profile import CapitalAllocationProfile
from .allocation_service import PortfolioAwareCapitalAllocationService
from .constraint_service import PortfolioConstraintValidationService

@dataclass(frozen=True)
class ScenarioComparisonResult:
    status:str
    recommended_scenario:str
    scenarios:tuple[dict[str,Any],...]
    rationale:tuple[str,...]
    def to_dict(self):return asdict(self)

class PortfolioConstructionScenarioService:
    def compare(self, positions:list[dict[str,Any]], registry:dict[str,Any]) -> ScenarioComparisonResult:
        configs=[('CONSERVATIVE',.30,.30),('BALANCED',.20,.50),('GROWTH',.10,.65)]
        out=[]
        for name,reserve,deployment in configs:
            alloc=PortfolioAwareCapitalAllocationService(CapitalAllocationProfile(reserve_cash_pct=reserve,maximum_deployment_pct=deployment)).allocate(positions,registry)
            constraints=PortfolioConstraintValidationService().validate(list(alloc.allocations),registry)
            score=(100 if constraints.valid else 0)+min(alloc.allocated_capital/ max(alloc.deployment_limit,1)*30,30)-len(constraints.violations)*20
            out.append({'name':name,'score':round(score,2),'allocation':alloc.to_dict(),'constraints':constraints.to_dict()})
        valid=[x for x in out if x['constraints']['valid']]
        chosen=max(valid or out,key=lambda x:x['score'])['name']
        return ScenarioComparisonResult('COMPLETE' if valid else 'REVIEW_REQUIRED',chosen,tuple(out),(f'{chosen} provides the strongest valid balance of deployment and constraints.',))
