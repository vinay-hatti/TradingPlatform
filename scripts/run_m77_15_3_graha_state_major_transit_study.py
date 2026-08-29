#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,random
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean,pstdev

from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.jpl_horizons_ephemeris import (
    fetch_geocentric_apparent_ecliptic_longitude,
    fetch_geocentric_ecliptic_state,
)

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"data/m77/m77_15_3_graha_state_daily_2000_2040.csv"
CACHE=ROOT/"reports/m77/m77_15_0_jpl_ephemeris_cache"
CERT=ROOT/"reports/m77/m77_15_3_graha_registry_certification.json"
OUT=ROOT/"reports/m77/m77_15_3_graha_state_major_transit_study.json"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"

VERSION="M77.15.3-GRAHA-STATE-MAJOR-TRANSIT-STUDY-1.0"
CERT_CONFIRM="CERTIFY_M77_15_3_GRAHA_REGISTRY"
RUN_CONFIRM="RUN_M77_15_3_GRAHA_STATE_STUDY"

TARGETS=("SPX","NDX","RUT")
PROXIES={"SPX":"SPY","NDX":"QQQ","RUT":"IWM"}
HORIZONS=(1,5,10,20,60)
OUTCOMES=("FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY",
          "MAX_ADVERSE_EXCURSION","MAX_FAVORABLE_EXCURSION",
          "TURNING_POINT_3_SESSION","REGIME_TRANSITION")
PLANETS=("MERCURY","VENUS","MARS","JUPITER","SATURN")
JPL_BODIES=("MERCURY","VENUS","MARS","JUPITER","SATURN")
FROZEN_CERT_DATES=(date(2023,3,20),date(2024,9,22),date(2025,12,1),date(2026,8,21))
JPL_MAX_ERROR_DEG=0.10
MIN_N=30
BOUNDARY_EXCLUSION_DEG=0.10
CIRCULAR_SHIFTS=1024
RNG_SEED=771530

FACTORS=(
    "MERCURY_RETROGRADE","VENUS_RETROGRADE","MARS_RETROGRADE","JUPITER_RETROGRADE","SATURN_RETROGRADE",
    "MERCURY_STATION_WINDOW_3D","VENUS_STATION_WINDOW_3D","MARS_STATION_WINDOW_3D","JUPITER_STATION_WINDOW_3D","SATURN_STATION_WINDOW_3D",
    "MERCURY_SUN_PROXIMITY_8DEG","VENUS_SUN_PROXIMITY_8DEG","MARS_SUN_PROXIMITY_8DEG","JUPITER_SUN_PROXIMITY_8DEG","SATURN_SUN_PROXIMITY_8DEG",
    "MARS_RASHI","JUPITER_RASHI","SATURN_RASHI",
    "JUPITER_NAKSHATRA","SATURN_NAKSHATRA",
    "RAHU_RASHI","RAHU_NAKSHATRA",
    "JUPITER_RASHI_INGRESS_WINDOW_3D","SATURN_RASHI_INGRESS_WINDOW_3D","RAHU_RASHI_INGRESS_WINDOW_3D",
)

def adist(a,b):
    d=abs((a%360)-(b%360))%360
    return min(d,360-d)

def bh(items):
    ordered=sorted(items,key=lambda x:x[1]); m=len(ordered); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(ordered,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q

def load_registry():
    out={}
    with REGISTRY.open() as f:
        for r in csv.DictReader(f):
            out[r["date"]]=r
    return out

def load_regimes():
    if not PIT.exists(): return {}
    x=json.loads(PIT.read_text())
    rows=x if isinstance(x,list) else x.get("snapshots") or x.get("rows") or []
    return {str(r.get("as_of"))[:10]:r.get("regime") for r in rows if r.get("as_of") and r.get("regime")}

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def certify(reg):
    rows=[]
    for d in FROZEN_CERT_DATES:
        rr=reg.get(d.isoformat())
        if not rr:
            raise SystemExit(f"registry missing frozen certification date {d}")
        for body in JPL_BODIES:
            app=fetch_geocentric_apparent_ecliptic_longitude(body,d,CACHE)
            geom=fetch_geocentric_ecliptic_state(body,d,CACHE)
            swiss=float(rr[f"{body.lower()}_tropical_deg"])
            jpl_app=float(app["observer_ecliptic_longitude_deg"])
            jpl_geom=float(geom["tropical_ecliptic_longitude_deg"])
            rows.append({
                "date":d.isoformat(),
                "body":body,
                "registry_apparent_tropical_deg":swiss,
                "jpl_apparent_ecliptic_of_date_deg":jpl_app,
                "apparent_angular_error_deg":adist(swiss,jpl_app),
                "jpl_geometric_vector_longitude_deg":jpl_geom,
                "geometric_vs_registry_diagnostic_error_deg":adist(swiss,jpl_geom),
            })
    maxerr=max(r["apparent_angular_error_deg"] for r in rows)
    max_geom_diag=max(r["geometric_vs_registry_diagnostic_error_deg"] for r in rows)
    out={"version":"M77.15.3.1-APPARENT-ECLIPTIC-PARITY-CORRECTION-1.0","status":"READY",
         "mode":"GRAHA_REGISTRY_JPL_APPARENT_ECLIPTIC_CERTIFICATION",
         "comparison_contract":"SWISS_APPARENT_GEOCENTRIC_VS_JPL_OBSERVER_QUANTITY_31_APPARENT_ECLIPTIC_OF_DATE",
         "comparisons":len(rows),"max_angular_error_deg":maxerr,
         "max_geometric_diagnostic_error_deg":max_geom_diag,
         "threshold_deg":JPL_MAX_ERROR_DEG,
         "rows":rows,"acceptance":{"jpl_registry_parity":maxerr<=JPL_MAX_ERROR_DEG,
         "financial_study_authorized":maxerr<=JPL_MAX_ERROR_DEG,"production_authority_effect":False},
         "production_authority_effect":False}
    write_json_atomic(CERT,out)
    return out

def require_cert():
    if not CERT.exists(): raise SystemExit("Run M77.15.3 certify before financial study")
    x=json.loads(CERT.read_text())
    if not x.get("acceptance",{}).get("financial_study_authorized"):
        raise SystemExit("M77.15.3 study blocked: Graha registry JPL parity not certified")

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
    r0=regimes.get(str(dates[i])[:10]); r1=regimes.get(str(dates[i+h])[:10])
    return {"FORWARD_RETURN":fwd,"ABSOLUTE_RETURN":abs(fwd),
      "REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
      "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0,
      "MAX_FAVORABLE_EXCURSION":max(path) if path else 0.0,
      "TURNING_POINT_3_SESSION":turning(close,i),
      "REGIME_TRANSITION":None if r0 is None or r1 is None else (1.0 if r0!=r1 else 0.0)}

def factor_value(row,factor):
    key=factor.lower()
    return row[key]

def factor_boundary_ok(row,factor):
    f=factor.lower()
    if f.endswith("_rashi"):
        base=f[:-6]
        return float(row[f"{base}_rashi_boundary_distance_deg"])>=BOUNDARY_EXCLUSION_DEG
    if f.endswith("_nakshatra"):
        base=f[:-10]
        return float(row[f"{base}_nakshatra_boundary_distance_deg"])>=BOUNDARY_EXCLUSION_DEG
    if "_sun_proximity_8deg" in f:
        base=f.split("_sun_proximity_8deg")[0]
        return float(row[f"{base}_sun8_boundary_distance_deg"])>=BOUNDARY_EXCLUSION_DEG
    return True

def matched_baseline(event,eligible,vals,dates,regimes):
    evset=set(event); diffs=[]
    for i in event:
        wd=dates[i].weekday(); mo=dates[i].month; reg=regimes.get(str(dates[i])[:10])
        c=[j for j in eligible if j not in evset and dates[j].weekday()==wd and dates[j].month==mo
           and (reg is None or regimes.get(str(dates[j])[:10])==reg)]
        if c: diffs.append(vals[i]-mean(vals[j] for j in c))
    return mean(diffs) if diffs else None

def circular_null(labels,eligible,vals,level,rng):
    n=len(eligible)
    if n<2:return []
    positions=[labels[i] for i in eligible]
    shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS: shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    out=[]
    for sh in shifts:
        vv=[vals[eligible[k]] for k in range(n) if positions[(k+sh)%n]==level]
        if vv: out.append(mean(vv))
    return out

def emp_p(obs,null):
    if not null:return 1.0
    c=mean(null); dev=abs(obs-c)
    return (1+sum(abs(x-c)>=dev for x in null))/(len(null)+1)

def run_study(reg):
    require_cert()
    regimes=load_regimes(); rng=random.Random(RNG_SEED); results=[]; pvals=[]
    with SessionLocal() as s: resolved={t:resolve(s,t) for t in TARGETS}
    with SessionLocal() as s:
      for target,sym in resolved.items():
        if not sym:continue
        rows=prices(s,sym); dates=[r[0] for r in rows]; close=[r[1] for r in rows]; dret=daily_returns(close)
        regrows={i:reg.get(str(d)[:10]) for i,d in enumerate(dates)}
        for h in HORIZONS:
          vectors={i:vector(close,dret,dates,regimes,i,h) for i in range(len(rows)-h) if regrows.get(i)}
          vectors={i:v for i,v in vectors.items() if v is not None}
          for factor in FACTORS:
            labels={i:factor_value(regrows[i],factor) for i in vectors if factor_boundary_ok(regrows[i],factor)}
            levels=sorted(set(labels.values()))
            for outcome in OUTCOMES:
              vals={i:vectors[i][outcome] for i in labels if vectors[i][outcome] is not None}
              eligible=sorted(vals)
              if not eligible:continue
              for level in levels:
                event=[i for i in eligible if labels.get(i)==level]
                if not event:continue
                ev=mean(vals[i] for i in event)
                evset=set(event); comp=[vals[i] for i in eligible if i not in evset]
                inc_comp=None if not comp else ev-mean(comp)
                inc_match=matched_baseline(event,eligible,vals,dates,regimes)
                null=circular_null(labels,eligible,vals,level,rng)
                p=emp_p(ev,null)
                key=f"{target}|{h}|{factor}|{level}|{outcome}"
                pvals.append((key,p))
                byy=defaultdict(list)
                for i in event:byy[dates[i].year].append(vals[i])
                yearly={str(y):{"n":len(vv),"mean":mean(vv)} for y,vv in byy.items() if len(vv)>=8}
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
              "matched_control_direction_consistency":sign_consistent,
              "full_year_raw_direction_consistency":year_consistent}
        r["research_gate"]=gate
        r["status"]="RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        supported+=r["status"]=="RESEARCH_SUPPORTED_CANDIDATE"
    out={"version":VERSION,"status":"READY","targets":resolved,"factors":FACTORS,"horizons":HORIZONS,
         "outcomes":OUTCOMES,"result_count":len(results),"research_supported_candidate_count":supported,
         "registry_certification":json.loads(CERT.read_text())["acceptance"],
         "governance":{"research_only":True,"single_factor_only":True,"factor_combinations":False,
         "neighboring_threshold_search":False,"sun_proximity_8deg_is_geometric_proxy_only":True,
         "database_read_only":True,"production_authority_effect":False,"automatic_promotion":False},
         "results":results,
         "next_step":"REVIEW_GRAHA_SURVIVORS_THEN_CONFIRM_ONLY_PREDECLARED_SURVIVORS",
         "production_authority_effect":False}
    write_json_atomic(OUT,out)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","certify","run")); ap.add_argument("--confirm"); a=ap.parse_args()
    reg=load_registry()
    if a.mode=="preflight":
        print(json.dumps({"version":VERSION,"status":"READY","registry_rows":len(reg),"factors":FACTORS,
          "targets":TARGETS,"horizons":HORIZONS,"outcomes":OUTCOMES,
          "certification_required":"JPL_APPARENT_ECLIPTIC_PARITY_BEFORE_FINANCIAL_STUDY",
          "certification_contract":"SWISS_APPARENT_GEOCENTRIC_VS_JPL_OBSERVER_QUANTITY_31_APPARENT_ECLIPTIC_OF_DATE",
          "jpl_max_error_deg":JPL_MAX_ERROR_DEG,"boundary_exclusion_deg":BOUNDARY_EXCLUSION_DEG,
          "sun_proximity_8deg_disposition":"GEOMETRIC_RESEARCH_PROXY_NOT_TRADITIONAL_COMBUSTION_AUTHORITY",
          "governance":{"single_factor_only":True,"factor_combinations":False,"neighboring_threshold_search":False,
          "database_writes":False,"production_authority_effect":False,"automatic_promotion":False}},indent=2));return
    if a.mode=="certify":
        if a.confirm!=CERT_CONFIRM:raise SystemExit(f"confirmation required: {CERT_CONFIRM}")
        o=certify(reg)
        print(json.dumps({"status":o["status"],"comparisons":o["comparisons"],
          "max_angular_error_deg":o["max_angular_error_deg"],"threshold_deg":o["threshold_deg"],
          "acceptance":o["acceptance"],"production_authority_effect":False},indent=2));return
    if a.confirm!=RUN_CONFIRM:raise SystemExit(f"confirmation required: {RUN_CONFIRM}")
    o=run_study(reg)
    print(json.dumps({"version":VERSION,"status":"READY","targets":o["targets"],"result_count":o["result_count"],
      "research_supported_candidate_count":o["research_supported_candidate_count"],
      "next_step":o["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__":main()
