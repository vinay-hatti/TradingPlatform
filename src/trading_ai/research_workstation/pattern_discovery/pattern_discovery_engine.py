from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from .pattern_discovery_policy import PatternDiscoveryPolicy
from .pattern_discovery_profile import PatternClusterProfile, PatternDiscoveryProfile, SimilarityMatchProfile, SimilarityReportProfile

class PatternDiscoveryEngine:
    def __init__(self, policy=None):
        self.policy=policy or PatternDiscoveryPolicy(); self.policy.validate()

    @staticmethod
    def _tags(case):
        return {str(getattr(t,"tag","")).strip().lower() for t in getattr(case,"tags",()) if str(getattr(t,"tag","")).strip()}

    def similarity_score(self,left,right):
        score=0.0; dims=[]
        checks=(("SYMBOL",left.symbol==right.symbol,self.policy.symbol_weight),("SECTOR",left.sector==right.sector,self.policy.sector_weight),("STRATEGY",left.strategy_name==right.strategy_name,self.policy.strategy_weight),("OUTCOME",left.outcome_status==right.outcome_status,self.policy.outcome_weight),("THESIS_STATUS",left.thesis_validation_status==right.thesis_validation_status,self.policy.thesis_status_weight))
        for name,ok,weight in checks:
            if ok: score+=weight; dims.append(name)
        lt,rt=self._tags(left),self._tags(right); shared=tuple(sorted(lt&rt)); union=lt|rt
        if shared: dims.append("TAGS")
        score += self.policy.tag_weight * (len(shared)/len(union) if union else 0.0)
        return round(score,6), shared, tuple(dims)

    def build_similarity_report(self, *, knowledge_base, report_id="M34-PHASE5-SIMILARITY-001", generated_at=None):
        cases=tuple(getattr(knowledge_base,"cases",())); matches=[]
        for left,right in combinations(cases,2):
            score,shared,dims=self.similarity_score(left,right)
            if score < self.policy.minimum_similarity_score: continue
            band="HIGH" if score>=self.policy.high_similarity_score else ("MODERATE" if score>=0.50 else "LOW")
            matches.append(SimilarityMatchProfile(left.case_id,right.case_id,score,band,shared,dims,right.outcome_status,right.thesis_validation_status,{"symmetric":True}))
        matches.sort(key=lambda x:x.similarity_score, reverse=True); matches=matches[:self.policy.maximum_matches]
        warnings=[]
        if len(cases)<2: warnings.append("At least two knowledge cases are required for pairwise similarity.")
        elif not matches: warnings.append("No case pair met the minimum similarity threshold.")
        return SimilarityReportProfile(report_id,generated_at or datetime.now(timezone.utc),len(cases),len(matches),tuple(matches),"READY" if len(cases)>=2 else "INSUFFICIENT_HISTORY",tuple(warnings),{"milestone":34,"phase":5,"step":2})

    @staticmethod
    def _dominant(values):
        values=[str(v or "UNKNOWN") for v in values]
        return Counter(values).most_common(1)[0][0] if values else "UNKNOWN"

    def _clusters(self,cases,ctype,getter):
        grouped=defaultdict(list)
        for case in cases: grouped[str(getter(case) or "UNKNOWN")].append(case)
        result=[]
        for key,members in sorted(grouped.items()):
            if len(members)<self.policy.minimum_cluster_size: continue
            success=sum(1 for m in members if m.outcome_status.upper() in {"PROFITABLE","SUCCESS","WIN"})/len(members)
            avg=sum(m.institutional_score for m in members)/len(members)
            counts=Counter(t.tag for m in members for t in m.tags)
            shared=tuple(sorted(k for k,v in counts.items() if v==len(members)))
            result.append(PatternClusterProfile(f"{ctype}-{key.upper().replace(' ','_')}",ctype,key,tuple(m.case_id for m in members),len(members),self._dominant(m.outcome_status for m in members),self._dominant(m.thesis_validation_status for m in members),round(avg,6),round(success,6),shared,{}))
        return result

    def build_pattern_discovery(self, *, knowledge_base, report_id="M34-PHASE5-PATTERN-001", generated_at=None):
        cases=tuple(getattr(knowledge_base,"cases",())); clusters=[]
        for ctype,getter in (("SECTOR",lambda x:x.sector),("STRATEGY",lambda x:x.strategy_name),("OUTCOME",lambda x:x.outcome_status),("THESIS_STATUS",lambda x:x.thesis_validation_status)):
            clusters.extend(self._clusters(cases,ctype,getter))
        clusters.sort(key=lambda x:(x.success_rate,x.average_institutional_score,x.case_count), reverse=True)
        strongest=tuple(f"{c.cluster_type}:{c.cluster_key} success_rate={c.success_rate:.3f} avg_score={c.average_institutional_score:.3f}" for c in clusters[:10])
        warnings=[]
        if len(cases)<self.policy.minimum_cluster_size: warnings.append("Insufficient history for pattern clustering.")
        elif not clusters: warnings.append("No qualifying clusters were discovered.")
        return PatternDiscoveryProfile(report_id,generated_at or datetime.now(timezone.utc),len(clusters),tuple(clusters),strongest,tuple(warnings),"READY" if len(cases)>=self.policy.minimum_cluster_size else "INSUFFICIENT_HISTORY",{"milestone":34,"phase":5,"step":2})
