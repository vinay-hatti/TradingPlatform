#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,math,random
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean,pstdev

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_15_7_long_history_replication.json"
OUT=ROOT/"reports/m77/m77_15_7_long_history_frozen_hypothesis_replication.json"

VERSION="M77.15.7-LONG-HISTORY-FROZEN-HYPOTHESIS-REPLICATION-1.0"
CONFIRM="RUN_M77_15_7_LONG_HISTORY_FROZEN_REPLICATION"
RNG_SEED=771570
CIRCULAR_SHIFTS=1024
DAILY_MIN_N=30
EVENT_MIN_N=8
BOUNDARY_EXCLUSION_DEG=0.10

PANCHANGA_FACTORS=("TITHI","PAKSHA","MOON_NAKSHATRA","MOON_RASHI","YOGA","KARANA")
GRAHA_FACTORS=(
    "MERCURY_RETROGRADE","VENUS_RETROGRADE","MARS_RETROGRADE","JUPITER_RETROGRADE","SATURN_RETROGRADE",
    "MERCURY_STATION_WINDOW_3D","VENUS_STATION_WINDOW_3D","MARS_STATION_WINDOW_3D","JUPITER_STATION_WINDOW_3D","SATURN_STATION_WINDOW_3D",
    "MERCURY_SUN_PROXIMITY_8DEG","VENUS_SUN_PROXIMITY_8DEG","MARS_SUN_PROXIMITY_8DEG","JUPITER_SUN_PROXIMITY_8DEG","SATURN_SUN_PROXIMITY_8DEG",
    "MARS_RASHI","JUPITER_RASHI","SATURN_RASHI",
    "JUPITER_NAKSHATRA","SATURN_NAKSHATRA",
    "RAHU_RASHI","RAHU_NAKSHATRA",
    "JUPITER_RASHI_INGRESS_WINDOW_3D","SATURN_RASHI_INGRESS_WINDOW_3D","RAHU_RASHI_INGRESS_WINDOW_3D",
)
EVENT_FAMILIES=(
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

def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))

def bh(items):
    ordered=sorted(items,key=lambda x:x[1]); m=len(ordered); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(ordered,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q

def turning(close,i,radius=3):
    if i<radius or i+radius>=len(close): return None
    w=close[i-radius:i+radius+1]
    return 1.0 if close[i]==min(w) or close[i]==max(w) else 0.0

def daily_returns(close):
    out=[None]
    for i in range(1,len(close)):
        out.append(close[i]/close[i-1]-1)
    return out

def vector(close,dret,i,h):
    if i+h>=len(close): return None
    fwd=close[i+h]/close[i]-1
    path=[close[j]/close[i]-1 for j in range(i+1,i+h+1)]
    rr=[x for x in dret[i+1:i+h+1] if x is not None]
    return {
        "FORWARD_RETURN":fwd,
        "ABSOLUTE_RETURN":abs(fwd),
        "REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
        "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0,
        "MAX_FAVORABLE_EXCURSION":max(path) if path else 0.0,
        "TURNING_POINT_3_SESSION":turning(close,i),
    }

def matched_baseline(event,eligible,vals,dates):
    evset=set(event); diffs=[]
    for i in event:
        wd=dates[i].weekday(); mo=dates[i].month
        c=[j for j in eligible if j not in evset and dates[j].weekday()==wd and dates[j].month==mo]
        if c:
            diffs.append(vals[i]-mean(vals[j] for j in c))
    return mean(diffs) if diffs else None

def circular_label_null(labels,eligible,vals,level,rng):
    n=len(eligible)
    if n<2:return []
    positions=[labels[i] for i in eligible]
    shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS:
        shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    out=[]
    for sh in shifts:
        vv=[vals[eligible[k]] for k in range(n) if positions[(k+sh)%n]==level]
        if vv: out.append(mean(vv))
    return out

def circular_event_null(event_idx,eligible,vals,rng):
    n=len(eligible)
    if n<2 or not event_idx:return []
    pos={idx:k for k,idx in enumerate(eligible)}
    base=[pos[i] for i in event_idx if i in pos]
    if not base:return []
    shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS:
        shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    return [mean(vals[eligible[(k+sh)%n]] for k in base) for sh in shifts]

def emp_p(obs,null):
    if not null:return 1.0
    c=mean(null); dev=abs(obs-c)
    return (1+sum(abs(x-c)>=dev for x in null))/(len(null)+1)

def load_recent_supported(cfg):
    out=set()
    direction={}
    for family,path in cfg["recent_canonical_artifacts"].items():
        p=ROOT/path
        if not p.exists(): continue
        x=json.loads(p.read_text())
        for r in x.get("results") or []:
            if r.get("status") in ("RESEARCH_SUPPORTED","RESEARCH_SUPPORTED_CANDIDATE"):
                k=r.get("key")
                if k:
                    out.add(k)
                    inc=r.get("incremental_vs_complement")
                    direction[k]=0 if inc is None else (1 if inc>0 else -1 if inc<0 else 0)
    return out,direction

def era_stats(event,eligible,vals,dates,eras):
    evset=set(event); result=[]
    for start,end in eras:
        ei=[i for i in event if start <= dates[i].isoformat() <= end]
        ci=[i for i in eligible if i not in evset and start <= dates[i].isoformat() <= end]
        if not ei or not ci:
            result.append({"era":[start,end],"event_n":len(ei),"incremental_vs_complement":None})
        else:
            result.append({
                "era":[start,end],
                "event_n":len(ei),
                "incremental_vs_complement":mean(vals[i] for i in ei)-mean(vals[i] for i in ci)
            })
    return result

def daily_factor_value(row,factor):
    return row[factor.lower()]

def daily_boundary_ok(row,factor):
    f=factor.lower()
    if f.endswith("_rashi"):
        base=f[:-6]
        key=f"{base}_rashi_boundary_distance_deg"
        return key not in row or float(row[key])>=BOUNDARY_EXCLUSION_DEG
    if f.endswith("_nakshatra"):
        base=f[:-10]
        key=f"{base}_nakshatra_boundary_distance_deg"
        return key not in row or float(row[key])>=BOUNDARY_EXCLUSION_DEG
    if "_sun_proximity_8deg" in f:
        base=f.split("_sun_proximity_8deg")[0]
        key=f"{base}_sun8_boundary_distance_deg"
        return key not in row or float(row[key])>=BOUNDARY_EXCLUSION_DEG
    return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    cfg=json.loads(CFG.read_text())
    cert=ROOT/cfg["required_authority_certification"]
    if not cert.exists():
        raise SystemExit("M77.15.6.5.2 authority certification missing")
    cx=json.loads(cert.read_text())
    if not cx.get("certified_for_m77_15_7_long_history_replication"):
        raise SystemExit("M77.15.7 blocked: M77.15.6.5.2 authority is not certified")

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "authority_type":cfg["authority_type"],
            "proxy_files":cfg["proxy_files"],
            "frozen_eras":cfg["frozen_eras"],
            "horizons":cfg["horizons"],
            "outcomes":cfg["outcomes"],
            "governance":{
                "frozen_hypotheses_only":True,
                "new_hypothesis_search":False,
                "pit_regime_control_in_long_history":False,
                "proxy_only_survivor_may_advance":False,
                "recent_canonical_confirmation_required":True,
                "database_writes":False,
                "production_authority_effect":False
            }
        },indent=2))
        return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    panch={r["date"]:r for r in load_csv(ROOT/cfg["frozen_hypothesis_sources"]["panchanga_registry"])}
    graha={r["date"]:r for r in load_csv(ROOT/cfg["frozen_hypothesis_sources"]["graha_registry"])}
    events=load_csv(ROOT/cfg["frozen_hypothesis_sources"]["event_registry"])
    recent_supported,recent_direction=load_recent_supported(cfg)

    results=[]
    pvals=[]
    rng=random.Random(RNG_SEED)

    for target,path in cfg["proxy_files"].items():
        rows=load_csv(ROOT/path)
        dates=[date.fromisoformat(r["date"]) for r in rows]
        close=[float(r["close"]) for r in rows]
        dret=daily_returns(close)
        date_to_idx={r["date"]:i for i,r in enumerate(rows)}

        # Frozen M77.15.2 Panchanga family.
        for h in cfg["horizons"]:
            vectors={i:vector(close,dret,i,h) for i in range(len(rows)-h)}
            for factor in PANCHANGA_FACTORS:
                labels={i:daily_factor_value(panch[rows[i]["date"]],factor)
                        for i in vectors if rows[i]["date"] in panch}
                levels=sorted(set(labels.values()))
                for outcome in cfg["outcomes"]:
                    vals={i:vectors[i][outcome] for i in labels if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    for level in levels:
                        event=[i for i in eligible if labels.get(i)==level]
                        if not event: continue
                        ev=mean(vals[i] for i in event)
                        evset=set(event); comp=[vals[i] for i in eligible if i not in evset]
                        inc=None if not comp else ev-mean(comp)
                        incm=matched_baseline(event,eligible,vals,dates)
                        null=circular_label_null(labels,eligible,vals,level,rng)
                        p=emp_p(ev,null)
                        key=f"{target}|{h}|{factor}|{level}|{outcome}"
                        eras=era_stats(event,eligible,vals,dates,cfg["frozen_eras"])
                        pvals.append((key,p))
                        results.append({
                            "family":"M77_15_2_PANCHANGA","key":key,"target":target,
                            "research_instrument":rows[0]["research_instrument"],
                            "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
                            "horizon_sessions":h,"factor":factor,"level":level,"outcome":outcome,
                            "event_n":len(event),"event_mean":ev,
                            "incremental_vs_complement":inc,
                            "incremental_vs_weekday_month":incm,
                            "circular_empirical_p":p,"era_stats":eras
                        })

        # Frozen M77.15.3 Graha family.
        for h in cfg["horizons"]:
            vectors={i:vector(close,dret,i,h) for i in range(len(rows)-h)}
            for factor in GRAHA_FACTORS:
                labels={i:daily_factor_value(graha[rows[i]["date"]],factor)
                        for i in vectors if rows[i]["date"] in graha and daily_boundary_ok(graha[rows[i]["date"]],factor)}
                levels=sorted(set(labels.values()))
                for outcome in cfg["outcomes"]:
                    vals={i:vectors[i][outcome] for i in labels if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    for level in levels:
                        event=[i for i in eligible if labels.get(i)==level]
                        if not event: continue
                        ev=mean(vals[i] for i in event)
                        evset=set(event); comp=[vals[i] for i in eligible if i not in evset]
                        inc=None if not comp else ev-mean(comp)
                        incm=matched_baseline(event,eligible,vals,dates)
                        null=circular_label_null(labels,eligible,vals,level,rng)
                        p=emp_p(ev,null)
                        key=f"{target}|{h}|{factor}|{level}|{outcome}"
                        eras=era_stats(event,eligible,vals,dates,cfg["frozen_eras"])
                        pvals.append((key,p))
                        results.append({
                            "family":"M77_15_3_GRAHA","key":key,"target":target,
                            "research_instrument":rows[0]["research_instrument"],
                            "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
                            "horizon_sessions":h,"factor":factor,"level":level,"outcome":outcome,
                            "event_n":len(event),"event_mean":ev,
                            "incremental_vs_complement":inc,
                            "incremental_vs_weekday_month":incm,
                            "circular_empirical_p":p,"era_stats":eras
                        })

        # Frozen M77.15.4 event families.
        for family in EVENT_FAMILIES:
            family_idx=[date_to_idx[e["event_date"]] for e in events
                        if e["event_family"]==family and e["event_date"] in date_to_idx]
            for h in cfg["horizons"]:
                vectors={i:vector(close,dret,i,h) for i in range(len(rows)-h)}
                for outcome in cfg["outcomes"]:
                    vals={i:vectors[i][outcome] for i in vectors if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    event=[i for i in family_idx if i in vals]
                    if not event: continue
                    ev=mean(vals[i] for i in event)
                    evset=set(event); comp=[vals[i] for i in eligible if i not in evset]
                    inc=None if not comp else ev-mean(comp)
                    incm=matched_baseline(event,eligible,vals,dates)
                    null=circular_event_null(event,eligible,vals,rng)
                    p=emp_p(ev,null)
                    key=f"{target}|{h}|{family}|{outcome}"
                    eras=era_stats(event,eligible,vals,dates,cfg["frozen_eras"])
                    pvals.append((key,p))
                    results.append({
                        "family":"M77_15_4_EVENT","key":key,"target":target,
                        "research_instrument":rows[0]["research_instrument"],
                        "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
                        "horizon_sessions":h,"event_family":family,"outcome":outcome,
                        "event_n":len(event),"event_mean":ev,
                        "incremental_vs_complement":inc,
                        "incremental_vs_weekday_month":incm,
                        "circular_empirical_p":p,"era_stats":eras
                    })

    qmap=bh(pvals)
    proxy_supported=0
    cross_supported=0

    for r in results:
        r["bh_q"]=qmap.get(r["key"],1.0)
        inc=r.get("incremental_vs_complement")
        incm=r.get("incremental_vs_weekday_month")
        same_controls=inc is not None and incm is not None and inc*incm>0

        era_incs=[e["incremental_vs_complement"] for e in r["era_stats"] if e["incremental_vs_complement"] is not None]
        sign=0 if inc is None else (1 if inc>0 else -1 if inc<0 else 0)
        supportive=sum(1 for x in era_incs if (1 if x>0 else -1 if x<0 else 0)==sign and sign!=0)
        eligible_eras=len(era_incs)

        min_n=EVENT_MIN_N if r["family"]=="M77_15_4_EVENT" else DAILY_MIN_N
        gate={
            "sample_size":r["event_n"]>=min_n,
            "bh_q_le_0_05":r["bh_q"]<=0.05,
            "matched_control_direction_consistency":same_controls,
            "at_least_3_eligible_eras":eligible_eras>=3,
            "majority_era_direction_consistency":supportive>=3,
        }
        r["long_history_gate"]=gate
        r["long_history_status"]="RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        if r["long_history_status"]=="RESEARCH_SUPPORTED_CANDIDATE":
            proxy_supported+=1

        canon=r["key"] in recent_supported
        canon_dir=recent_direction.get(r["key"],0)
        long_dir=sign
        r["cross_authority"]={
            "recent_canonical_supported_counterpart":canon,
            "recent_canonical_direction":canon_dir,
            "long_history_direction":long_dir,
            "same_direction":bool(canon and canon_dir!=0 and canon_dir==long_dir),
        }
        r["cross_authority_status"]="SUPPORTED_FOR_DEPENDENCE_ROBUST_CONFIRMATION" if (
            r["long_history_status"]=="RESEARCH_SUPPORTED_CANDIDATE"
            and r["cross_authority"]["same_direction"]
        ) else "NOT_PROMOTABLE"
        if r["cross_authority_status"]=="SUPPORTED_FOR_DEPENDENCE_ROBUST_CONFIRMATION":
            cross_supported+=1

    out={
        "version":VERSION,
        "status":"READY",
        "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
        "authority_certification":{
            "source":str(cert),
            "common_start":cx["common_authority"]["first_date"],
            "common_end":cx["common_authority"]["last_date"],
            "common_sessions":cx["common_authority"]["session_count"],
        },
        "result_count":len(results),
        "long_history_research_supported_candidate_count":proxy_supported,
        "cross_authority_supported_for_dependence_robust_confirmation_count":cross_supported,
        "recent_canonical_supported_key_count":len(recent_supported),
        "frozen_eras":cfg["frozen_eras"],
        "governance":{
            "frozen_hypotheses_only":True,
            "new_hypothesis_search":False,
            "pit_regime_control_in_long_history":False,
            "proxy_only_survivor_may_not_advance":True,
            "recent_canonical_confirmation_required":True,
            "same_effect_direction_required":True,
            "automatic_production_promotion":False,
            "database_writes":False,
            "production_authority_effect":False,
        },
        "results":results,
        "next_step":"DEPENDENCE_ROBUST_CONFIRMATION_ONLY_FOR_CROSS_AUTHORITY_SURVIVORS"
            if cross_supported else "NO_PROMOTABLE_CROSS_AUTHORITY_SURVIVORS_REVIEW_LONG_HISTORY_DIAGNOSTICS",
        "production_authority_effect":False,
    }
    write_json_atomic(OUT,out)

    print(json.dumps({
        "version":VERSION,
        "status":"READY",
        "authority_type":out["authority_type"],
        "authority_common_sessions":out["authority_certification"]["common_sessions"],
        "result_count":out["result_count"],
        "long_history_research_supported_candidate_count":proxy_supported,
        "recent_canonical_supported_key_count":len(recent_supported),
        "cross_authority_supported_for_dependence_robust_confirmation_count":cross_supported,
        "next_step":out["next_step"],
        "production_authority_effect":False
    },indent=2))

if __name__=="__main__":
    main()
