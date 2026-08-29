from __future__ import annotations
from collections import defaultdict,deque
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import mean

def pctile(vals,v):
 c=sorted(float(x) for x in vals if x is not None)
 return None if not c else sum(x<=v for x in c)/len(c)*100.0

def daily_dates(sessions,start,end,warmup=252,horizon=60):
 s=sorted(set(sessions))
 return [d for i,d in enumerate(s) if start<=d<=end and i>=warmup and i+horizon<len(s)]

def monthly_dates(sessions,start,end):
 m={}
 for d in sorted(set(sessions)):
  if start<=d<=end:m[(d.year,d.month)]=d
 return [m[k] for k in sorted(m)]

def features(series):
 out={};cl=[];vh=[];prev=None;r=deque(maxlen=20)
 for d,c in series:
  c=float(c);cl.append(c)
  if prev is not None and prev>0:r.append(c/prev-1)
  prev=c
  s50=mean(cl[-50:]) if len(cl)>=50 else None;s200=mean(cl[-200:]) if len(cl)>=200 else None
  ret=(c/cl[-21]-1)*100 if len(cl)>=21 else None;vol=None
  if len(r)>=20:
   z=list(r);mu=mean(z);vol=sqrt(sum((x-mu)**2 for x in z)/max(1,len(z)-1))*sqrt(252)*100;vh.append(vol)
  out[d]={"close":c,"sma50":s50,"sma200":s200,"ret20":ret,"vol20":vol,"vol_percentile":pctile(vh[-252:],vol) if vol is not None else None,"above50":None if s50 is None else c>s50}
 return out

def snapshot(price_rows,as_of):
 by=defaultdict(list)
 for sym,d,c in price_rows:
  if d<=as_of and c is not None and float(c)>0:by[str(sym)].append((d,float(c)))
 f={s:features(sorted(v)) for s,v in by.items()};spy=f.get("SPY",{}).get(as_of)
 if not spy:return {"as_of":str(as_of),"regime":"UNKNOWN"}
 breadth=[x[as_of]["above50"] for s,x in f.items() if s not in {"SPX","NDX","RUT"} and as_of in x and x[as_of]["above50"] is not None]
 b=sum(breadth)/len(breadth)*100 if breadth else None
 close,s50,s200,ret=spy["close"],spy["sma50"],spy["sma200"],spy["ret20"]
 trend="UNKNOWN" if None in (close,s50,s200,ret) else ("BULL_TREND" if close>s50>s200 and ret>0 else "BEAR_TREND" if close<s50<s200 and ret<0 else "TRANSITION_UP" if close>s50 and s50<=s200 else "TRANSITION_DOWN" if close<s50 and s50>=s200 else "RANGE_MIXED")
 vp=spy["vol_percentile"];vol="UNKNOWN" if vp is None else "EXTREME" if vp>=90 else "HIGH" if vp>=75 else "LOW" if vp<=25 else "NORMAL"
 bs="UNKNOWN" if b is None else "BROAD_STRONG" if b>=65 else "BROAD_WEAK" if b<=35 else "MIXED"
 stressed=vol in {"HIGH","EXTREME"}
 regime="UNKNOWN" if "UNKNOWN" in (trend,vol,bs) else ("BULL_STRESSED" if trend=="BULL_TREND" and (stressed or bs=="BROAD_WEAK") else "BULL_HEALTHY" if trend=="BULL_TREND" else "BEAR_STRESSED" if trend=="BEAR_TREND" and stressed else "BEAR_ORDERLY" if trend=="BEAR_TREND" else trend if trend in {"TRANSITION_UP","TRANSITION_DOWN"} else "RANGE_STRESSED" if stressed else "RANGE_NORMAL")
 return {"as_of":str(as_of),"regime":regime,"trend_state":trend,"volatility_state":vol,"breadth_state":bs,"spy_close":close,"spy_sma50":s50,"spy_sma200":s200,"spy_return20_pct":ret,"spy_realized_vol20_pct":spy["vol20"],"vol20_percentile_252":vp,"breadth_above_50d_pct":b,"breadth_eligible_symbols":len(breadth)}
