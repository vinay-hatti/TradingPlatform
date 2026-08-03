from __future__ import annotations
from datetime import datetime,timezone
from statistics import fmean
from typing import Any
from .contracts import *
from .providers import IntelligenceProviderRegistry

def _now(): return datetime.now(timezone.utc).isoformat()
def _payload(opp): return dict(opp.get('source_payload') or {})
def _n(p,*keys,default=None):
    for k in keys:
        v=p.get(k)
        if isinstance(v,(int,float)): return float(v)
    return default

class ExplanationEngine:
    def build(self,scores:tuple[IntelligenceScore,...])->Explanation:
        ev=sorted((e for s in scores for e in s.evidence),key=lambda e:abs(e.contribution),reverse=True)
        pos=tuple(e for e in ev if e.score>=60)[:6]; neg=tuple(e for e in ev if e.score<60)[:6]
        conf=fmean([s.confidence for s in scores]) if scores else 0
        invalid=tuple(f'{s.name} score falls below 50' for s in scores if s.overall_score>=50)[:6]
        checklist=tuple({'category':s.category.value,'label':s.name,'passed':s.overall_score>=60,'score':round(s.overall_score,2)} for s in scores)
        lead=', '.join(e.source for e in pos[:3]) or 'No strong drivers'
        return Explanation(f'Opportunity is primarily supported by {lead}.',conf,pos,neg,invalid,checklist)

class RecommendationEngine:
    def build(self,scores):
        values=sorted((r for s in scores for r in s.recommendations),key=lambda r:(r.priority,-r.confidence))
        return tuple(values[:8])

class TradePlaybookEngine:
    def build(self,opp,scores)->TradePlaybook:
        p=_payload(opp); spot=_n(p,'spot_price','underlying_price','spot','price'); atr=_n(p,'atr14','atr',default=(spot*.025 if spot else None)); direction=str(opp.get('direction','CALL')).upper(); score=fmean([s.overall_score for s in scores]) if scores else 50
        if spot is not None and atr is not None:
            bullish=direction in {'CALL','BULLISH','LONG'}; stop=spot-(1.5*atr) if bullish else spot+(1.5*atr); targets=(spot+(2*atr),spot+(3*atr)) if bullish else (spot-(2*atr),spot-(3*atr))
        else: stop=None;targets=()
        strategy='LONG_CALL' if direction in {'CALL','BULLISH','LONG'} else 'LONG_PUT'; alt='BULL_CALL_SPREAD' if strategy=='LONG_CALL' else 'BEAR_PUT_SPREAD'
        return TradePlaybook(strategy,alt,spot,stop,targets,int(_n(p,'expected_hold_days',default=8) or 8),min(.95,max(.05,score/100)),min(5,max(.25,(score-40)/12)),int(_n(p,'contracts',default=0) or 0) or None,{k:p.get(k) for k in ('delta','gamma','theta','vega')},tuple(r.description for s in scores for r in s.risks)[:5])

class OpportunityHealthEngine:
    def build(self,opp,scores)->OpportunityHealth:
        current=fmean([s.overall_score for s in scores]) if scores else 50; p=_payload(opp); baseline=_n(p,'ai_score','score','total_score',default=current) or current; delta=current-baseline; direction='IMPROVING' if delta>=3 else 'DETERIORATING' if delta<=-3 else 'STABLE'; drivers=tuple({'category':s.category.value,'score':round(s.overall_score,2),'direction':s.trend} for s in scores)
        action='ADVANCE REVIEW' if current>=75 else 'MONITOR' if current>=55 else 'REASSESS OR ARCHIVE'
        return OpportunityHealth(round(current,2),direction,round(baseline,2),drivers,action)

class InstitutionalIntelligenceService:
    VERSION='m55.1'
    def __init__(self,registry=None): self.registry=registry or IntelligenceProviderRegistry();self.explain=ExplanationEngine();self.recommend=RecommendationEngine();self.playbooks=TradePlaybookEngine();self.health=OpportunityHealthEngine()
    def generate(self,opp:dict[str,Any])->IntelligenceBundle:
        scores=self.registry.publish_all(opp); explanation=self.explain.build(scores); recommendations=self.recommend.build(scores); playbook=self.playbooks.build(opp,scores); health=self.health.build(opp,scores)
        strongest=max(scores,key=lambda x:x.overall_score); profile={'primary_profile':f'{strongest.name} {opp.get("direction","Directional")}', 'risk_profile':'LOW' if health.score>=80 else 'MEDIUM' if health.score>=60 else 'HIGH','preferred_strategy':playbook.preferred_strategy,'secondary_profile':playbook.alternative_strategy}
        return IntelligenceBundle(str(opp['opportunity_id']),str(opp['snapshot_id']),str(opp['snapshot_timestamp']),self.VERSION,_now(),scores,explanation,recommendations,playbook,health,profile)
