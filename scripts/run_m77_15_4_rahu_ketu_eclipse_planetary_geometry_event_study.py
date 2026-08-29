#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,math,random
from collections import defaultdict
from pathlib import Path
from statistics import mean,pstdev

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

ROOT=Path(__file__).resolve().parents[1]
EVENTS=ROOT/"data/m77/m77_15_4_astronomical_event_registry_2000_2040.csv"
OUT=ROOT/"reports/m77/m77_15_4_rahu_ketu_eclipse_planetary_geometry_event_study.json"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"

VERSION="M77.15.4-RAHU-KETU-ECLIPSE-PLANETARY-GEOMETRY-EVENT-STUDY-1.0"
CONFIRM="RUN_M77_15_4_EVENT_STUDY"

TARGETS=("SPX","NDX","RUT")
PROXIES={"SPX":"SPY","NDX":"QQQ","RUT":"IWM"}
POST_HORIZONS=(1,5,10,20,60)
OUTCOMES=("FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY",
          "MAX_ADVERSE_EXCURSION","MAX_FAVORABLE_EXCURSION",
          "TURNING_POINT_3_SESSION","REGIME_TRANSITION")
MIN_N=8
CIRCULAR_SHIFTS=1024
RNG_SEED=771540

FROZEN_FAMILIES=(
"SOLAR_ECLIPSE","LUNAR_ECLIPSE",
"JUPITER_SATURN_CONJUNCTION","JUPITER_SATURN_SQUARE","JUPITER_SATURN_TRINE","JUPITER_SATURN_OPPOSITION",
"JUPITER_RAHU_CONJUNCTION","JUPITER_RAHU_SQUARE","JUPITER_RAHU_TRINE","JUPITER_RAHU_OPPOSITION",
"SATURN_RAHU_CONJUNCTION","SATURN_RAHU_SQUARE","SATURN_RAHU_TRINE","SATURN_RAHU_OPPOSITION",
)

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def bh(items):
    ordered=sorted(items,key=lambda x:x[1]); m=len(ordered); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(ordered,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q

def load_events():
    rows=[]
    with EVENTS.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

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

def outcome_vector(close,dret,dates,regimes,i,h):
    if i+h>=len(close): return None
    fwd=close[i+h]/close[i]-1
    path=[close[j]/close[i]-1 for j in range(i+1,i+h+1)]
    rr=[x for x in dret[i+1:i+h+1] if x is not None]
    r0=regimes.get(str(dates[i])[:10]); r1=regimes.get(str(dates[i+h])[:10])
    return {
        "FORWARD_RETURN":fwd,
        "ABSOLUTE_RETURN":abs(fwd),
        "REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
        "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0,
        "MAX_FAVORABLE_EXCURSION":max(path) if path else 0.0,
        "TURNING_POINT_3_SESSION":turning(close,i),
        "REGIME_TRANSITION":None if r0 is None or r1 is None else (1.0 if r0!=r1 else 0.0),
    }

def matched_baseline(event_idx,eligible,vals,dates,regimes):
    ev=set(event_idx); diffs=[]
    for i in event_idx:
        wd=dates[i].weekday(); mo=dates[i].month; reg=regimes.get(str(dates[i])[:10])
        c=[j for j in eligible if j not in ev and dates[j].weekday()==wd and dates[j].month==mo
           and (reg is None or regimes.get(str(dates[j])[:10])==reg)]
        if c:
            diffs.append(vals[i]-mean(vals[j] for j in c))
    return mean(diffs) if diffs else None

def circular_event_null(event_idx,eligible,vals,rng):
    n=len(eligible)
    if n<2 or not event_idx:return []
    pos={idx:k for k,idx in enumerate(eligible)}
    base=[pos[i] for i in event_idx if i in pos]
    if not base:return []
    shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS:
        shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    out=[]
    for sh in shifts:
        shifted=[eligible[(k+sh)%n] for k in base]
        out.append(mean(vals[i] for i in shifted))
    return out

def emp_p(obs,null):
    if not null:return 1.0
    c=mean(null); dev=abs(obs-c)
    return (1+sum(abs(x-c)>=dev for x in null))/(len(null)+1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    events=load_events()
    counts=defaultdict(int)
    for e in events: counts[e["event_family"]]+=1

    with SessionLocal() as s:
        resolved={t:resolve(s,t) for t in TARGETS}

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "targets":resolved,
            "event_families":FROZEN_FAMILIES,
            "event_family_counts":dict(counts),
            "post_event_horizons":POST_HORIZONS,
            "outcomes":OUTCOMES,
            "governance":{
                "event_study_only":True,
                "daily_category_sweep":False,
                "event_orb_retuning":False,
                "event_window_retuning":False,
                "factor_combinations":False,
                "weekday_month_pit_regime_matched_controls":True,
                "circular_event_calendar_null":True,
                "multiple_testing":"BENJAMINI_HOCHBERG",
                "database_writes":False,
                "production_authority_effect":False,
                "automatic_promotion":False
            }
        },indent=2))
        return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    regimes=load_regimes()
    rng=random.Random(RNG_SEED)
    results=[]
    pvals=[]

    with SessionLocal() as s:
      for target,sym in resolved.items():
        if not sym: continue
        rows=prices(s,sym)
        dates=[r[0] for r in rows]
        close=[r[1] for r in rows]
        dret=daily_returns(close)
        by_date={str(d)[:10]:i for i,d in enumerate(dates)}

        for family in FROZEN_FAMILIES:
            event_idx=[]
            for e in events:
                if e["event_family"]!=family: continue
                i=by_date.get(e["event_date"])
                if i is not None:
                    event_idx.append(i)

            for h in POST_HORIZONS:
                vectors={}
                for i in range(len(rows)-h):
                    v=outcome_vector(close,dret,dates,regimes,i,h)
                    if v is not None:
                        vectors[i]=v

                for outcome in OUTCOMES:
                    vals={i:vectors[i][outcome] for i in vectors if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    ev=[i for i in event_idx if i in vals]
                    if not ev:
                        continue

                    event_mean=mean(vals[i] for i in ev)
                    evset=set(ev)
                    comp=[vals[i] for i in eligible if i not in evset]
                    inc_comp=None if not comp else event_mean-mean(comp)
                    inc_match=matched_baseline(ev,eligible,vals,dates,regimes)
                    null=circular_event_null(ev,eligible,vals,rng)
                    p=emp_p(event_mean,null)

                    byy=defaultdict(list)
                    for i in ev:
                        byy[dates[i].year].append(vals[i])
                    yearly={str(y):{"n":len(vv),"mean":mean(vv)} for y,vv in byy.items()}

                    key=f"{target}|{h}|{family}|{outcome}"
                    pvals.append((key,p))
                    results.append({
                        "key":key,"target":target,"price_symbol":sym,
                        "event_family":family,"event_n":len(ev),
                        "horizon_sessions":h,"outcome":outcome,
                        "event_mean":event_mean,
                        "incremental_vs_complement":inc_comp,
                        "incremental_vs_weekday_month_regime":inc_match,
                        "circular_empirical_p":p,"null_n":len(null),
                        "yearly":yearly
                    })

    q=bh(pvals)
    supported=0
    for r in results:
        r["bh_q"]=q.get(r["key"],1.0)
        incs=[x for x in (r.get("incremental_vs_complement"),r.get("incremental_vs_weekday_month_regime")) if x is not None]
        sign_consistent=len(incs)==2 and incs[0]*incs[1]>0
        eligible_years=[v for v in r["yearly"].values() if v["n"]>=1]
        gate={
            "sample_size":r["event_n"]>=MIN_N,
            "bh_q_le_0_05":r["bh_q"]<=0.05,
            "matched_control_direction_consistency":sign_consistent,
            "at_least_3_event_years":len(eligible_years)>=3,
        }
        r["research_gate"]=gate
        r["status"]="RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        supported += r["status"]=="RESEARCH_SUPPORTED_CANDIDATE"

    out={
        "version":VERSION,
        "status":"READY",
        "targets":resolved,
        "event_family_counts":dict(counts),
        "result_count":len(results),
        "research_supported_candidate_count":supported,
        "governance":{
            "research_only":True,
            "event_study_only":True,
            "no_posthoc_orb_or_window_retuning":True,
            "database_read_only":True,
            "production_authority_effect":False,
            "automatic_promotion":False
        },
        "results":results,
        "next_step":"REVIEW_EVENT_SURVIVORS_THEN_DEPENDENCE_ROBUST_CONFIRMATION_ONLY_FOR_PREDECLARED_SURVIVORS",
        "production_authority_effect":False,
    }
    write_json_atomic(OUT,out)
    print(json.dumps({
        "version":VERSION,
        "status":"READY",
        "targets":resolved,
        "result_count":len(results),
        "research_supported_candidate_count":supported,
        "next_step":out["next_step"],
        "production_authority_effect":False
    },indent=2))

if __name__=="__main__":
    main()
