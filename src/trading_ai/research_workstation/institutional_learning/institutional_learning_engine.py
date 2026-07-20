from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt
from typing import Any, Callable, Iterable
from .institutional_learning_policy import InstitutionalLearningPolicy
from .institutional_learning_profile import LearningFactorProfile, LearningSummaryProfile, InstitutionalLearningProfile

class InstitutionalLearningEngine:
    SUCCESS = {"PROFITABLE","SUCCESS","WIN","CONFIRMED"}
    FAILURE = {"LOSS","FAILED","INVALIDATED"}
    def __init__(self, policy: InstitutionalLearningPolicy | None = None):
        self.policy = policy or InstitutionalLearningPolicy(); self.policy.validate()
    @staticmethod
    def _is_success(case: Any) -> bool:
        return str(getattr(case,"outcome_status","UNKNOWN")).upper() in InstitutionalLearningEngine.SUCCESS
    @staticmethod
    def _prob(case: Any) -> float:
        value = getattr(case,"predicted_probability",None)
        if value is None: value = getattr(case,"institutional_score",0.5)
        return max(0.0,min(1.0,float(value or 0.5)))
    def _factor_rows(self, cases: tuple[Any,...], factor_type: str, key_fn: Callable[[Any], Iterable[str]]) -> tuple[LearningFactorProfile,...]:
        groups=defaultdict(list)
        for case in cases:
            for key in key_fn(case):
                key=str(key or "UNKNOWN").strip()
                if key: groups[key].append(case)
        rows=[]
        for key,members in groups.items():
            if len(members)<self.policy.minimum_factor_occurrences: continue
            successes=sum(self._is_success(c) for c in members); failures=len(members)-successes
            posterior=(successes+self.policy.prior_alpha)/(len(members)+self.policy.prior_alpha+self.policy.prior_beta)
            avg=sum(float(getattr(c,"institutional_score",0) or 0) for c in members)/len(members)
            raw=posterior-0.5; adj=max(-self.policy.maximum_adjustment,min(self.policy.maximum_adjustment,raw))
            rec="INCREASE_CONFIDENCE" if posterior>=self.policy.high_confidence_threshold else "REDUCE_CONFIDENCE" if posterior<=self.policy.low_confidence_threshold else "MAINTAIN_CONFIDENCE"
            rows.append(LearningFactorProfile(factor_type,key,len(members),successes,failures,round(posterior,6),round(avg,6),round(adj,6),rec,{}))
        return tuple(sorted(rows,key=lambda r:(r.posterior_success_probability,r.occurrences),reverse=True))
    def build(self, *, knowledge_base: Any, report_id: str="M34-PHASE5-LEARNING-001", generated_at: datetime|None=None) -> InstitutionalLearningProfile:
        cases=tuple(getattr(knowledge_base,"cases",()))
        strategy=self._factor_rows(cases,"STRATEGY",lambda c:(getattr(c,"strategy_name","UNKNOWN"),))
        sector=self._factor_rows(cases,"SECTOR",lambda c:(getattr(c,"sector","UNKNOWN"),))
        outcome=self._factor_rows(cases,"THESIS_STATUS",lambda c:(getattr(c,"thesis_validation_status","UNKNOWN"),))
        tags=self._factor_rows(cases,"TAG",lambda c:tuple(getattr(t,"tag","") for t in getattr(c,"tags",())))
        success=sum(self._is_success(c) for c in cases); failed=len(cases)-success
        probs=[self._prob(c) for c in cases]; actual=[1.0 if self._is_success(c) else 0.0 for c in cases]
        brier=sum((p-y)**2 for p,y in zip(probs,actual))/len(cases) if cases else 0.0
        cal=abs((sum(probs)/len(probs) if probs else 0.0)-(success/len(cases) if cases else 0.0))
        global_adj=max(-self.policy.maximum_adjustment,min(self.policy.maximum_adjustment,(success/len(cases)-sum(probs)/len(probs)) if cases else 0.0))
        allrows=tuple(strategy+sector+outcome+tags)
        positive=tuple(f"{r.factor_type}:{r.factor_key}" for r in sorted(allrows,key=lambda r:r.posterior_success_probability,reverse=True)[:5] if r.posterior_success_probability>0.5)
        negative=tuple(f"{r.factor_type}:{r.factor_key}" for r in sorted(allrows,key=lambda r:r.posterior_success_probability)[:5] if r.posterior_success_probability<0.5)
        rec=[]
        if global_adj>0.02: rec.append("Increase future confidence modestly when supported by matching learned factors.")
        elif global_adj<-0.02: rec.append("Reduce future confidence until calibration improves.")
        else: rec.append("Maintain current global confidence calibration.")
        if negative: rec.append("Require stronger evidence for historically weak factors: "+", ".join(negative[:3]))
        if positive: rec.append("Use historically strong factors as bounded supporting priors: "+", ".join(positive[:3]))
        status="READY" if len(cases)>=self.policy.minimum_cases else "INSUFFICIENT_HISTORY"
        warnings=() if status=="READY" else (f"At least {self.policy.minimum_cases} completed cases are required.",)
        summary=LearningSummaryProfile(len(cases),success,failed,round(success/len(cases),6) if cases else 0.0,round(brier,6),round(cal,6),round(global_adj,6),positive,negative)
        return InstitutionalLearningProfile(report_id,generated_at or datetime.now(timezone.utc),status,strategy,sector,outcome,tags,summary,tuple(rec),warnings,{"milestone":34,"phase":5,"step":3})
