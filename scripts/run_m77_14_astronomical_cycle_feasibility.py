#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.astronomical_cycles import features,FROZEN_HYPOTHESES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/m77/m77_14_astronomical_cycle_feasibility.json"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"
HORIZONS=(1,5,10,20,60); TARGETS=("SPX","NDX","RUT")
PROXIES={"SPX":"SPY","NDX":"QQQ","RUT":"IWM"}; MIN_N=30
SHIFTS=(-61,-43,-29,-17,17,29,43,61)

def stats(v):
    if len(v)<2:return {"n":len(v)}
    mu=mean(v); var=sum((x-mu)**2 for x in v)/(len(v)-1); se=math.sqrt(var/len(v))
    z=0 if se==0 else mu/se
    return {"n":len(v),"mean_return_pct":mu*100,"hit_rate_pct":100*sum(x>0 for x in v)/len(v),
            "p":1.0 if se==0 else math.erfc(abs(z)/math.sqrt(2))}
def bh(items):
    o=sorted(items,key=lambda x:x[1]); m=len(o); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(o,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q
def regimes():
    if not PIT.exists():return {}
    x=json.loads(PIT.read_text()); rows=x if isinstance(x,list) else x.get("snapshots") or x.get("rows") or []
    return {str(r.get("as_of"))[:10]:r.get("regime") for r in rows if r.get("as_of")}
def resolve(s,t):
    for sym in (t,PROXIES[t],"I:"+t):
        if s.execute(text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),{"s":sym}).scalar():return sym
def prices(s,sym):
    return [(r[0],float(r[1])) for r in s.execute(text("SELECT date,close FROM price_history WHERE symbol=:s AND close IS NOT NULL ORDER BY date"),{"s":sym})]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","run")); ap.add_argument("--confirm"); a=ap.parse_args()
    with SessionLocal() as s: resolved={t:resolve(s,t) for t in TARGETS}
    if a.mode=="preflight":
        print(json.dumps({"version":"M77.14-ASTRONOMICAL-CYCLE-FEASIBILITY-1.0","status":"READY",
          "confirmation_required":"RUN_M77_14_ASTRONOMICAL_FEASIBILITY","targets":resolved,"horizons":HORIZONS,
          "hypotheses":FROZEN_HYPOTHESES,"production_authority_effect":False,
          "traditional_ephemeris_gate":"EXPLORATORY_LOW_PRECISION_NOT_PROMOTABLE_WITHOUT_INDEPENDENT_PARITY"},indent=2)); return
    if a.confirm!="RUN_M77_14_ASTRONOMICAL_FEASIBILITY":raise SystemExit("confirmation required")
    reg=regimes(); results=[]; pvals=[]
    with SessionLocal() as s:
      for target,sym in resolved.items():
        if not sym:continue
        rows=prices(s,sym); dates=[x[0] for x in rows]; close=[x[1] for x in rows]; ff=[features(d) for d in dates]
        for h in HORIZONS:
          for hyp,meta in FROZEN_HYPOTHESES.items():
            vals=[]; years=defaultdict(list); regs=defaultdict(list)
            for i in range(len(rows)-h):
                if ff[i].get(hyp):
                    ret=close[i+h]/close[i]-1; vals.append(ret); years[dates[i].year].append(ret)
                    if reg.get(str(dates[i])[:10]):regs[reg[str(dates[i])[:10]]].append(ret)
            st=stats(vals); key=f"{target}|{h}|{hyp}"; pvals.append((key,st.get("p",1)))
            mask=[bool(x.get(hyp)) for x in ff]; placebo=[]
            for sh in SHIFTS:
                pv=[close[i+h]/close[i]-1 for i in range(len(rows)-h) if 0<=i+sh<len(mask) and mask[i+sh]]
                if pv:placebo.append(mean(pv))
            st["placebo_mean_return_pct"]=None if not placebo else mean(placebo)*100
            st["incremental_vs_placebo_pct"]=None if not placebo or "mean_return_pct" not in st else st["mean_return_pct"]-mean(placebo)*100
            results.append({"key":key,"target":target,"price_symbol":sym,"horizon_sessions":h,"hypothesis":hyp,
              "family":meta["family"],"overall":st,
              "full_year":{str(y):stats(v) for y,v in years.items() if len(v)>=MIN_N},
              "by_regime":{k:stats(v) for k,v in regs.items() if len(v)>=MIN_N}})
    q=bh(pvals); supported=0
    for r in results:
        r["bh_q"]=q.get(r["key"],1); o=r["overall"]; ys=r["full_year"]
        same=sum(1 for v in ys.values() if v.get("mean_return_pct",0)*o.get("mean_return_pct",0)>0)
        gate={"sample_size":o.get("n",0)>=MIN_N,"bh_q_le_0_05":r["bh_q"]<=.05,
          "placebo_increment_abs_ge_0_10pct":abs(o.get("incremental_vs_placebo_pct") or 0)>=.10,
          "full_year_consistency":len(ys)>=2 and same>=2,
          "independent_ephemeris_parity":r["family"]=="LUNAR"}
        r["research_gate"]=gate; r["status"]="RESEARCH_SUPPORTED" if all(gate.values()) else "UNSUPPORTED"
        supported+=r["status"]=="RESEARCH_SUPPORTED"
    out={"version":"M77.14-ASTRONOMICAL-CYCLE-FEASIBILITY-1.0","status":"READY",
      "governance":{"research_only":True,"database_read_only":True,"database_writes":False,
        "production_authority_effect":False,"automatic_promotion":False},
      "targets":resolved,"horizons":HORIZONS,"frozen_hypotheses":FROZEN_HYPOTHESES,
      "multiple_testing":"BENJAMINI_HOCHBERG","placebo_session_shifts":SHIFTS,
      "result_count":len(results),"research_supported_count":supported,"results":results,
      "traditional_astrology_disposition":"EXPLORATORY_ONLY_PENDING_INDEPENDENT_EPHEMERIS_PARITY",
      "next_step":"REVIEW_FEASIBILITY; ADD_INDEPENDENT_EPHEMERIS_PARITY_BEFORE_TRADITIONAL_ASTROLOGY_CERTIFICATION",
      "production_authority_effect":False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,indent=2,default=str)+"\n")
    print(json.dumps({k:out[k] for k in ("version","status","targets","result_count","research_supported_count","traditional_astrology_disposition","next_step","production_authority_effect")},indent=2))
if __name__=="__main__":main()
