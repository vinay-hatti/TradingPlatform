from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from .contracts import *

def _num(payload:dict[str,Any], names:tuple[str,...], default:float=50.0)->float:
    for name in names:
        value=payload.get(name)
        if isinstance(value,(int,float)): return max(0.0,min(100.0,float(value)))
    return default

def _sev(score:float)->Severity:
    return Severity.POSITIVE if score>=75 else Severity.NEUTRAL if score>=55 else Severity.WATCH if score>=40 else Severity.NEGATIVE

class IntelligenceProvider(ABC):
    category: IntelligenceCategory; priority:int=100
    @abstractmethod
    def publish(self, opportunity:dict[str,Any])->IntelligenceScore: ...

class PayloadScoreProvider(IntelligenceProvider):
    def __init__(self,category:IntelligenceCategory,name:str,fields:tuple[str,...],weight:float,priority:int): self.category=category;self.name=name;self.fields=fields;self.weight=weight;self.priority=priority
    def publish(self,opportunity:dict[str,Any])->IntelligenceScore:
        payload=dict(opportunity.get('source_payload') or {})
        score=_num(payload,self.fields)
        confidence=_num(payload,tuple(f'{x}_confidence' for x in self.fields),max(55.0,score-5))/100
        title=f'{self.name} evidence'
        evidence=(Evidence(self.name,title,f'{self.name} contributes {score:.1f}/100 from the persisted scanner snapshot.',score,self.weight,score*self.weight,confidence,_sev(score),opportunity.get('snapshot_timestamp')),)
        risks=() if score>=60 else (IntelligenceRisk(self.category.value,f'{self.name} is below the institutional quality threshold.',min(1,(60-score)/60),0.7,_sev(score),'Require confirmation or reduce position size.'),)
        rec=(Recommendation(f'{self.name} posture',self.priority,'PROCEED' if score>=65 else 'MONITOR',f'{self.name} score is {score:.1f}.',confidence,(title,)),)
        return IntelligenceScore(self.category,self.name,score,confidence,min(99,max(1,score)), 'IMPROVING' if score>=75 else 'STABLE', 'SUPPORTIVE' if score>=65 else 'CAUTION',_sev(score),evidence,risks,rec,{f:self._safe(payload.get(f)) for f in self.fields})
    @staticmethod
    def _safe(value): return value if isinstance(value,(str,int,float,bool)) or value is None else str(value)

DEFAULT_PROVIDERS=(
 PayloadScoreProvider(IntelligenceCategory.MARKET,'Market Context',('market_score','market_confirmation_score','breadth_score'),0.12,20),
 PayloadScoreProvider(IntelligenceCategory.TREND,'Trend Intelligence',('trend_score','trend_quality','trend_confidence'),0.18,10),
 PayloadScoreProvider(IntelligenceCategory.TRANSITION,'Transition Intelligence',('transition_score','transition_confirmation','breakout_score'),0.10,30),
 PayloadScoreProvider(IntelligenceCategory.DEALER,'Dealer Positioning',('dealer_score','dealer_positioning_score','gex_score'),0.12,20),
 PayloadScoreProvider(IntelligenceCategory.INSTITUTIONAL,'Institutional Participation',('institutional_score','institutional_conviction','leadership_score'),0.16,10),
 PayloadScoreProvider(IntelligenceCategory.LIQUIDITY,'Liquidity',('liquidity_score','options_quality_score'),0.10,20),
 PayloadScoreProvider(IntelligenceCategory.RISK,'Risk Quality',('risk_score','risk_reward_score'),0.08,10),
 PayloadScoreProvider(IntelligenceCategory.PROBABILITY,'Probability',('probability','win_probability','confidence'),0.07,20),
 PayloadScoreProvider(IntelligenceCategory.AI,'AI Ranking',('ai_score','score','total_score'),0.07,10),
)

class IntelligenceProviderRegistry:
    def __init__(self,providers=DEFAULT_PROVIDERS): self._providers=sorted(providers,key=lambda x:(x.priority,x.category.value))
    def publish_all(self,opportunity:dict[str,Any])->tuple[IntelligenceScore,...]: return tuple(provider.publish(opportunity) for provider in self._providers)
