from dataclasses import dataclass
from enum import Enum
class Phase2ClosureStatus(str,Enum): READY="READY"; DEGRADED="DEGRADED"; REVIEW="REVIEW"; FAILED="FAILED"
@dataclass(frozen=True)
class Phase2ClosureProfile:
    coverage_status:str; freshness_status:str; completeness_status:str; quality_status:str
    overall_status:Phase2ClosureStatus; production_approved:bool
    warnings:tuple[str,...]=(); rejection_reasons:tuple[str,...]=()
class Phase2ClosureEngine:
    rank={"READY":0,"DEGRADED":1,"REVIEW":2,"FAILED":3}
    def evaluate(self,coverage_status,freshness_status,completeness_status,quality_status):
        vals={k:self._n(v) for k,v in {"coverage":coverage_status,"freshness":freshness_status,"completeness":completeness_status,"quality":quality_status}.items()}
        worst=max(vals.values(),key=lambda x:self.rank[x])
        warnings=tuple(f"{k.title()} governance status is {v}." for k,v in vals.items() if v!="READY")
        rejects=("Phase 2 market-data governance is not production approved.",) if worst=="FAILED" else ()
        return Phase2ClosureProfile(vals["coverage"],vals["freshness"],vals["completeness"],vals["quality"],Phase2ClosureStatus(worst),worst in {"READY","DEGRADED"},warnings,rejects)
    def _n(self,v):
        n=str(getattr(v,"value",v)).strip().upper()
        if n not in self.rank: raise ValueError(f"Unsupported governance status: {v!r}")
        return n
