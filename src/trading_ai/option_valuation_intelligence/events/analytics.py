from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from statistics import mean, median, pstdev
from typing import Iterable
@dataclass(frozen=True)
class Distribution:
    sample_size:int; mean:float; median:float; stddev:float; p10:float; p25:float; p75:float; p90:float; maximum:float; minimum:float
def percentile(values:list[float],q:float)->float:
    if not values:return 0.0
    s=sorted(map(float,values));p=(len(s)-1)*q;lo=int(p);hi=min(lo+1,len(s)-1);w=p-lo;return s[lo]*(1-w)+s[hi]*w
def distribution(values:Iterable[float])->Distribution|None:
    v=[abs(float(x)) for x in values if x is not None]
    if not v:return None
    return Distribution(len(v),mean(v),median(v),pstdev(v) if len(v)>1 else 0.0,percentile(v,.1),percentile(v,.25),percentile(v,.75),percentile(v,.9),max(v),min(v))
def weighted_expected_move(implied,historical,forecast,weights=(.55,.30,.15)):
    names=('implied','historical','forecast'); vals=(implied,historical,forecast); a=[(n,float(v),w) for n,v,w in zip(names,vals,weights) if v is not None and float(v)>0]
    if not a:return None,{n:0.0 for n in names}
    t=sum(w for _,_,w in a);e={n:0.0 for n in names}
    for n,_,w in a:e[n]=w/t
    return sum(v*w for _,v,w in a)/t,e
def event_variance_move(event_iv,event_dte,baseline_iv=None,baseline_dte=None):
    a=max(0,event_iv)**2*max(1,event_dte)/365;b=0 if not baseline_iv or not baseline_dte else max(0,baseline_iv)**2*max(1,baseline_dte)/365;return sqrt(max(0,a-b))*100
def confidence_score(*,date_confirmed,time_confirmed,implied,historical_samples,forecast,liquidity_score,agreement_score,source_fresh):
    s=15+(12 if date_confirmed else 0)+(5 if time_confirmed else 0)+(22 if implied else 0)+min(18,historical_samples*2)+(8 if forecast else 0)+max(0,min(10,liquidity_score/10))+max(0,min(7,agreement_score/14.2857))+(3 if source_fresh else 0);return round(max(0,min(100,s)),2)
def classify_event_edge(implied,expected,confidence):
    if not implied or not expected:return 'INSUFFICIENT_DATA'
    edge=(expected-implied)/implied*100
    if confidence<50:return 'LOW_CONFIDENCE'
    if edge>=15:return 'UNDERPRICED_EVENT'
    if edge<=-15:return 'OVERPRICED_EVENT'
    return 'FAIRLY_PRICED'
