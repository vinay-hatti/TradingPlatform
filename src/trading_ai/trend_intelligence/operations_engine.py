from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import math
from pathlib import Path
from statistics import mean
from typing import Any
from .operations_contracts import Finding, OperationalAssessment
from .operations_policy import TrendOperationsPolicy
from .operations_serialization import read_json

def now_iso() -> str: return datetime.now(timezone.utc).isoformat()
def _status(payload: Any) -> str: return str(payload.get('status','MISSING')).upper() if isinstance(payload,dict) else 'MISSING'
def _symbols(payload: Any) -> list[dict]:
    if not isinstance(payload,dict): return []
    x=payload.get('symbols',[])
    return x if isinstance(x,list) else list(x.values()) if isinstance(x,dict) else []
def _num(v, default=0.0):
    try: return float(v)
    except (TypeError,ValueError): return default

def psi(current: list[float], baseline: list[float], bins: int=10) -> float:
    if len(current)<2 or len(baseline)<2: return 0.0
    lo=min(current+baseline); hi=max(current+baseline)
    if hi<=lo: return 0.0
    eps=1e-6; total=0.0
    for i in range(bins):
        a=lo+(hi-lo)*i/bins; b=lo+(hi-lo)*(i+1)/bins
        cp=sum(a<=x<(b if i<bins-1 else b+eps) for x in current)/len(current)
        bp=sum(a<=x<(b if i<bins-1 else b+eps) for x in baseline)/len(baseline)
        cp=max(cp,eps); bp=max(bp,eps); total+=(cp-bp)*math.log(cp/bp)
    return total

def js_divergence(a: dict[str,int], b: dict[str,int]) -> float:
    keys=set(a)|set(b)
    if not keys: return 0.0
    sa=sum(a.values()) or 1; sb=sum(b.values()) or 1
    out=0.0
    for k in keys:
        p=a.get(k,0)/sa; q=b.get(k,0)/sb; m=(p+q)/2
        if p: out += .5*p*math.log(p/m)
        if q: out += .5*q*math.log(q/m)
    return out

class TrendOperationsEngine:
    def __init__(self, root: Path, policy: TrendOperationsPolicy|None=None):
        self.root=root; self.policy=policy or TrendOperationsPolicy()
        self.report=root/'reports/trend_intelligence'
    def load(self):
        return {
          'base':read_json(self.report/'latest.json',{}),
          'transition':read_json(self.report/'transitions_latest.json',{}),
          'forecast':read_json(self.report/'forecasts_latest.json',{}),
          'institutional':read_json(self.report/'institutional_latest.json',{}),
          'platform':read_json(self.report/'platform_integration_latest.json',{}),
          'lifecycle':read_json(self.root/'reports/market_ingestion/lifecycle_latest.json',{}),
          'publication':read_json(self.root/'reports/published_state/current.json',{}),
        }
    def health(self,d):
        findings=[]; components={k:_status(v) for k,v in d.items() if k!='publication'}
        pub=_status(d['publication']); usable=bool(d['publication'].get('usable',False)) if isinstance(d['publication'],dict) else False
        if pub=='DEGRADED' and usable: components['publication']='DEGRADED_USABLE'
        else: components['publication']=pub
        weights={'base':15,'transition':15,'forecast':15,'institutional':15,'platform':20,'lifecycle':10,'publication':10}
        score=0
        for k,w in weights.items():
            s=components[k]
            if s=='READY': score+=w
            elif s in ('DEGRADED_USABLE','NO_NEW_DATA'): score+=w*.8
            elif s=='DEGRADED': score+=w*.5
            else: findings.append(Finding(f'{k.upper()}_NOT_READY','ERROR',f'{k} status is {s}',True,k))
        status='FAILED' if any(f.blocking for f in findings) else ('READY' if score>=self.policy.minimum_health_score else 'DEGRADED')
        return OperationalAssessment('health',status,score,now_iso(),{'components':components,'publication_usable':usable},findings)
    def calibration(self,d):
        forecasts=_symbols(d['forecast']); samples=[]
        for x in forecasts:
            realized=x.get('realized_direction') or x.get('outcome_direction')
            predicted=x.get('forecast_direction') or x.get('direction')
            confidence=_num(x.get('confidence'),0.5)
            if realized is not None and predicted is not None: samples.append((str(predicted),str(realized),confidence))
        n=len(samples); findings=[]
        if n<self.policy.minimum_calibration_samples:
            findings.append(Finding('INSUFFICIENT_REALIZED_OUTCOMES','INFO',f'{n} realized forecast outcomes; {self.policy.minimum_calibration_samples} required.',False,'calibration'))
            return OperationalAssessment('calibration','NOT_ENOUGH_HISTORY',100.0,now_iso(),{'sample_count':n,'minimum_samples':self.policy.minimum_calibration_samples,'fabricated_metrics':False},findings)
        accuracy=mean(1.0 if p==r else 0.0 for p,r,_ in samples)
        brier=mean((c-(1.0 if p==r else 0.0))**2 for p,r,c in samples)
        score=max(0,100*(accuracy-(brier*.25)))
        return OperationalAssessment('calibration','READY' if score>=60 else 'DEGRADED',score,now_iso(),{'sample_count':n,'directional_accuracy':accuracy,'brier_score':brier},findings)
    def drift(self,d,history):
        current=_symbols(d['platform']); values=[]; states=Counter()
        for x in current:
            values.append(_num(x.get('scanner_adjustment',x.get('decision_adjustment',0))))
            states[str(x.get('transition_state','UNKNOWN'))]+=1
        baseline=[]; base_states=Counter()
        for h in history[-30:]:
            m=h.get('metrics',{}); baseline.extend(m.get('adjustment_values',[])); base_states.update(m.get('transition_distribution',{}))
        p=psi(values,baseline); js=js_divergence(states,base_states); findings=[]
        status='READY'; score=100
        if baseline:
            if p>=self.policy.critical_psi or js>=self.policy.critical_js: status='DEGRADED'; score=50; findings.append(Finding('CRITICAL_DRIFT','WARNING','Critical drift threshold exceeded.',False,'drift',{'psi':p,'js':js}))
            elif p>=self.policy.warning_psi or js>=self.policy.warning_js: status='DEGRADED'; score=75; findings.append(Finding('DRIFT_WARNING','WARNING','Drift warning threshold exceeded.',False,'drift',{'psi':p,'js':js}))
        else: findings.append(Finding('BASELINE_BUILDING','INFO','No prior Phase 6 drift baseline; current snapshot establishes it.',False,'drift'))
        return OperationalAssessment('drift',status,score,now_iso(),{'psi':p,'jensen_shannon':js,'adjustment_values':values,'transition_distribution':dict(states),'baseline_snapshot_count':len(history[-30:])},findings)
    def attribution(self,d):
        rows=[]
        for x in _symbols(d['platform']):
            symbol=x.get('symbol')
            comps={
             'base_trend':_num(x.get('base_trend_adjustment',x.get('trend_adjustment',0))),
             'transition':_num(x.get('transition_adjustment',0)),
             'forecast':_num(x.get('forecast_adjustment',0)),
             'institutional':_num(x.get('institutional_adjustment',0)),
            }
            final=_num(x.get('decision_adjustment',x.get('scanner_adjustment',sum(comps.values()))))
            rows.append({'symbol':symbol,'components':comps,'component_total':sum(comps.values()),'final_adjustment':final,'residual':final-sum(comps.values())})
        score=100 if rows else 0; findings=[] if rows else [Finding('NO_ATTRIBUTION_SYMBOLS','ERROR','Platform context contained no symbols.',True,'attribution')]
        return OperationalAssessment('attribution','READY' if rows else 'FAILED',score,now_iso(),{'symbol_count':len(rows),'symbols':rows},findings)
    def governance(self,d):
        findings=[]; checks=[]
        required=('base','transition','forecast','institutional','platform')
        for name in required:
            p=d[name]; exists=isinstance(p,dict) and bool(p); status=_status(p)
            ok=exists and status=='READY'
            checks.append({'name':name,'status':'PASS' if ok else 'FAIL','observed_status':status})
            if not ok: findings.append(Finding(f'{name.upper()}_GOVERNANCE_FAILURE','ERROR',f'{name} is missing or not READY.',True,name))
        symbols=_symbols(d['platform']); canonical=all(bool(str(x.get('symbol','')).strip()) for x in symbols)
        checks.append({'name':'symbol_identity','status':'PASS' if canonical else 'FAIL','symbol_count':len(symbols)})
        if not canonical: findings.append(Finding('SYMBOL_IDENTITY_INVALID','ERROR','Blank symbol identity found.',True,'platform'))
        score=100*sum(c['status']=='PASS' for c in checks)/len(checks)
        status='FAILED' if any(f.blocking for f in findings) else ('READY' if score>=self.policy.minimum_governance_score else 'DEGRADED')
        return OperationalAssessment('governance',status,score,now_iso(),{'schema_version':self.policy.schema_version,'checks':checks},findings)
