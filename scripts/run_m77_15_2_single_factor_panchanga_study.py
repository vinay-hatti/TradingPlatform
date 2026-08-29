#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,random
from collections import defaultdict
from pathlib import Path
from statistics import mean,pstdev

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"data/m77/m77_15_2_panchanga_daily_2000_2040.csv"
OUT=ROOT/"reports/m77/m77_15_2_single_factor_panchanga_study.json"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"

VERSION="M77.15.2-SINGLE-FACTOR-PANCHANGA-STUDY-1.0"
CONFIRM="RUN_M77_15_2_SINGLE_FACTOR_PANCHANGA_STUDY"

TARGETS=("SPX","NDX","RUT")
PROXIES={"SPX":"SPY","NDX":"QQQ","RUT":"IWM"}
HORIZONS=(1,5,10,20,60)
OUTCOMES=("FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY",
          "MAX_ADVERSE_EXCURSION","MAX_FAVORABLE_EXCURSION",
          "TURNING_POINT_3_SESSION","REGIME_TRANSITION")
FACTORS=("TITHI","PAKSHA","MOON_NAKSHATRA","MOON_RASHI","YOGA","KARANA","VARA")
MIN_N=30
BOUNDARY_EXCLUSION_DEG=0.10
CIRCULAR_SHIFTS=1024
RNG_SEED=771520

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)


# VARA is explicitly a conventional calendar control, not a Vedic-supported feature.
VEDIC_FACTORS=set(FACTORS)-{"VARA"}

def bh(items):
    ordered=sorted(items,key=lambda x:x[1]); m=len(ordered); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(ordered,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q

def load_registry():
    out={}
    with REGISTRY.open() as f:
        for r in csv.DictReader(f):
            out[r["date"]]={
              "TITHI":r["tithi"],"PAKSHA":r["paksha"],"MOON_NAKSHATRA":r["moon_nakshatra"],
              "MOON_RASHI":r["moon_rashi"],"YOGA":r["yoga"],"KARANA":r["karana"],"VARA":r["vara"],
              "_boundary":float(r["min_category_boundary_distance_deg"])
            }
    return out

def load_regimes():
    if not PIT.exists(): return {}
    x=json.loads(PIT.read_text())
    rows=x if isinstance(x,list) else x.get("snapshots") or x.get("rows") or []
    return {str(r.get("as_of"))[:10]:r.get("regime") for r in rows if r.get("as_of") and r.get("regime")}

def resolve(s,target):
    for sym in (target,PROXIES[target],"I:"+target):
        if s.execute(text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),{"s":sym}).scalar():
            return sym

def prices(s,sym):
    return [(r[0],float(r[1])) for r in s.execute(text(
        "SELECT date,close FROM price_history WHERE symbol=:s AND close IS NOT NULL ORDER BY date"),{"s":sym})]

def daily_returns(close):
    out=[None]
    for i in range(1,len(close)): out.append(close[i]/close[i-1]-1)
    return out

def turning(close,i,radius=3):
    if i<radius or i+radius>=len(close): return None
    w=close[i-radius:i+radius+1]
    return 1.0 if close[i]==min(w) or close[i]==max(w) else 0.0

def vector(close,dret,dates,regimes,i,h):
    if i+h>=len(close): return None
    fwd=close[i+h]/close[i]-1
    path=[close[j]/close[i]-1 for j in range(i+1,i+h+1)]
    rr=[x for x in dret[i+1:i+h+1] if x is not None]
    reg0=regimes.get(str(dates[i])[:10]); reg1=regimes.get(str(dates[i+h])[:10])
    return {
      "FORWARD_RETURN":fwd,
      "ABSOLUTE_RETURN":abs(fwd),
      "REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
      "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0,
      "MAX_FAVORABLE_EXCURSION":max(path) if path else 0.0,
      "TURNING_POINT_3_SESSION":turning(close,i),
      "REGIME_TRANSITION":None if reg0 is None or reg1 is None else (1.0 if reg0!=reg1 else 0.0),
    }

def matched_baseline(event_idx,eligible,vals,dates,regimes):
    event=set(event_idx); diffs=[]
    for i in event_idx:
        wd=dates[i].weekday(); mo=dates[i].month; reg=regimes.get(str(dates[i])[:10])
        candidates=[j for j in eligible if j not in event and dates[j].weekday()==wd and dates[j].month==mo
                    and (reg is None or regimes.get(str(dates[j])[:10])==reg)]
        if candidates: diffs.append(vals[i]-mean(vals[j] for j in candidates))
    return mean(diffs) if diffs else None

def circular_null(labels,eligible,vals,level,rng,shifts):
    n=len(eligible)
    if n<2:return []
    positions=[labels[i] for i in eligible]
    shift_candidates=list(range(1,n))
    if len(shift_candidates)>shifts: shift_candidates=rng.sample(shift_candidates,shifts)
    out=[]
    for sh in shift_candidates:
        vv=[vals[eligible[k]] for k in range(n) if positions[(k+sh)%n]==level]
        if vv: out.append(mean(vv))
    return out

def emp_p(obs,null):
    if not null:return 1.0
    c=mean(null); dev=abs(obs-c)
    return (1+sum(abs(x-c)>=dev for x in null))/(len(null)+1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","run")); ap.add_argument("--confirm"); a=ap.parse_args()
    reg=load_registry(); regimes=load_regimes()
    with SessionLocal() as s: resolved={t:resolve(s,t) for t in TARGETS}
    if a.mode=="preflight":
        print(json.dumps({"version":VERSION,"status":"READY","confirmation_required":CONFIRM,
          "targets":resolved,"horizons":HORIZONS,"outcomes":OUTCOMES,"factors":FACTORS,
          "boundary_exclusion_deg":BOUNDARY_EXCLUSION_DEG,"circular_shift_nulls_per_test_max":CIRCULAR_SHIFTS,
          "vara_disposition":"CALENDAR_CONTROL_ONLY_NEVER_VEDIC_SUPPORTED",
          "governance":{"single_factor_only":True,"factor_combinations":False,"neighboring_category_search":False,
            "weekday_month_pit_regime_matched_controls":True,"multiple_testing":"BENJAMINI_HOCHBERG",
            "database_writes":False,"production_authority_effect":False,"automatic_promotion":False}},indent=2)); return
    if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")

    rng=random.Random(RNG_SEED); results=[]; pvals=[]
    with SessionLocal() as s:
      for target,sym in resolved.items():
        if not sym: continue
        rows=prices(s,sym); dates=[r[0] for r in rows]; close=[r[1] for r in rows]; dret=daily_returns(close)
        labels={}
        boundary={}
        for i,d in enumerate(dates):
            rr=reg.get(str(d)[:10])
            if rr:
                labels[i]=rr; boundary[i]=rr["_boundary"]
        for h in HORIZONS:
            vectors={}
            for i in range(len(rows)-h):
                if i not in labels or boundary[i]<BOUNDARY_EXCLUSION_DEG: continue
                v=vector(close,dret,dates,regimes,i,h)
                if v is not None:vectors[i]=v
            for factor in FACTORS:
                factor_labels={i:labels[i][factor] for i in vectors}
                levels=sorted(set(factor_labels.values()))
                for outcome in OUTCOMES:
                    vals={i:vectors[i][outcome] for i in vectors if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    if not eligible: continue
                    for level in levels:
                        event=[i for i in eligible if factor_labels.get(i)==level]
                        if not event: continue
                        ev=mean(vals[i] for i in event)
                        comp=[vals[i] for i in eligible if i not in set(event)]
                        inc_comp=None if not comp else ev-mean(comp)
                        inc_match=matched_baseline(event,eligible,vals,dates,regimes)
                        null=circular_null(factor_labels,eligible,vals,level,rng,CIRCULAR_SHIFTS)
                        p=emp_p(ev,null)
                        key=f"{target}|{h}|{factor}|{level}|{outcome}"
                        pvals.append((key,p))
                        yearly={}
                        byy=defaultdict(list)
                        for i in event: byy[dates[i].year].append(vals[i])
                        for y,vv in byy.items():
                            if len(vv)>=8: yearly[str(y)]={"n":len(vv),"mean":mean(vv)}
                        results.append({"key":key,"target":target,"price_symbol":sym,"horizon_sessions":h,
                          "factor":factor,"level":level,"outcome":outcome,"event_n":len(event),"event_mean":ev,
                          "incremental_vs_complement":inc_comp,"incremental_vs_weekday_month_regime":inc_match,
                          "circular_empirical_p":p,"null_n":len(null),"yearly":yearly})
    q=bh(pvals); supported=0
    for r in results:
        r["bh_q"]=q.get(r["key"],1.0)
        incs=[x for x in (r.get("incremental_vs_complement"),r.get("incremental_vs_weekday_month_regime")) if x is not None]
        sign_consistent=len(incs)==2 and incs[0]*incs[1]>0
        yearly=list(r["yearly"].values()); overall=r["event_mean"]
        year_consistent=len(yearly)>=2 and sum(1 for y in yearly if y["mean"]*overall>0)>=2
        gate={"sample_size":r["event_n"]>=MIN_N,"bh_q_le_0_05":r["bh_q"]<=.05,
          "matched_control_direction_consistency":sign_consistent,"full_year_raw_direction_consistency":year_consistent,
          "not_vara_calendar_control":r["factor"]!="VARA"}
        r["research_gate"]=gate
        r["status"]="RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        supported+=r["status"]=="RESEARCH_SUPPORTED_CANDIDATE"
    out={"version":VERSION,"status":"READY","registry_rows":len(reg),"targets":resolved,"horizons":HORIZONS,
      "outcomes":OUTCOMES,"factors":FACTORS,"result_count":len(results),"research_supported_candidate_count":supported,
      "vara_disposition":"CALENDAR_CONTROL_ONLY","governance":{"research_only":True,"database_read_only":True,
      "production_authority_effect":False,"automatic_promotion":False,"single_factor_only":True},
      "results":results,"next_step":"REVIEW_SINGLE_FACTOR_SURVIVORS_THEN_BUILD_INCREMENTAL_YEARLY_HARDENING_ONLY_FOR_PREDECLARED_SURVIVORS",
      "production_authority_effect":False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    write_json_atomic(OUT,out)
    print(json.dumps({"version":VERSION,"status":"READY","targets":resolved,"result_count":len(results),
      "research_supported_candidate_count":supported,"next_step":out["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__": main()
