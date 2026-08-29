#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,math,random
from datetime import date
from pathlib import Path
from statistics import mean,pstdev

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_16_3_h3_long_history_financial_study.json"
OUT=ROOT/"reports/m77/m77_16_3_h3_long_history_financial_study.json"
CONFIRM="RUN_M77_16_3_H3_LONG_HISTORY_FINANCIAL_STUDY"
RNG_SEED=771630

def load_csv(p):
    with Path(p).open() as f:
        return list(csv.DictReader(f))

def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n")
    json.loads(t.read_text())
    t.replace(p)

def bh(items):
    s=sorted(items,key=lambda x:x[1]); m=len(s); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(s,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q

def returns(c):
    return [None]+[c[i]/c[i-1]-1 for i in range(1,len(c))]

def vector(c,r,i,h):
    if i+h>=len(c): return None
    f=c[i+h]/c[i]-1
    path=[c[j]/c[i]-1 for j in range(i+1,i+h+1)]
    rr=[x for x in r[i+1:i+h+1] if x is not None]
    return {
        "ABSOLUTE_RETURN":abs(f),
        "REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
        "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0
    }

def matched(event,eligible,vals,dates):
    ev=set(event); diffs=[]
    for i in event:
        candidates=[j for j in eligible if j not in ev and dates[j].weekday()==dates[i].weekday() and dates[j].month==dates[i].month]
        if candidates:
            diffs.append(vals[i]-mean(vals[j] for j in candidates))
    return mean(diffs) if diffs else None

def circular_null(labels,eligible,vals,rng,max_shifts):
    n=len(eligible)
    if n<2:return []
    labs=[labels[i] for i in eligible]
    shifts=list(range(1,n))
    if len(shifts)>max_shifts:
        shifts=rng.sample(shifts,max_shifts)
    out=[]
    for sh in shifts:
        v=[vals[eligible[k]] for k in range(n) if labs[(k+sh)%n]]
        if v: out.append(mean(v))
    return out

def empirical_p(obs,null):
    if not null:return 1.0
    c=mean(null); d=abs(obs-c)
    return (1+sum(abs(x-c)>=d for x in null))/(len(null)+1)

def direction(x):
    return 0 if x is None or x==0 else (1 if x>0 else -1)

def era_stats(event,eligible,vals,dates,eras):
    ev=set(event); out=[]
    for a,b in eras:
        ei=[i for i in event if a<=dates[i].isoformat()<=b]
        ci=[i for i in eligible if i not in ev and a<=dates[i].isoformat()<=b]
        inc=None if not ei or not ci else mean(vals[i] for i in ei)-mean(vals[i] for i in ci)
        out.append({"era":[a,b],"event_n":len(ei),"incremental_vs_complement":inc})
    return out

def as_bool(v):
    return str(v).strip().lower() in ("1","true","t","yes","y")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    cfg=json.loads(CFG.read_text())
    meta=ROOT/cfg["required_feature_metadata"]
    auth=ROOT/cfg["required_long_history_certification"]
    if not meta.exists(): raise SystemExit("M77.16.3 blocked: M77.16.2 feature metadata missing")
    if not auth.exists(): raise SystemExit("M77.16.3 blocked: long-history authority certification missing")
    mx=json.loads(meta.read_text()); ax=json.loads(auth.read_text())
    if not mx.get("certified_for_h3_financial_study"):
        raise SystemExit("M77.16.3 blocked: H3 astronomical features are not certified")
    if not ax.get("certified_for_m77_15_7_long_history_replication"):
        raise SystemExit("M77.16.3 blocked: material long-history authority not certified")
    if ax["common_authority"]["session_count"]<cfg["authority"]["minimum_common_sessions"]:
        raise SystemExit("M77.16.3 blocked: insufficient long-history sessions")

    if a.mode=="preflight":
        print(json.dumps({
            "version":cfg["version"],"status":"READY","confirmation_required":CONFIRM,
            "feature_rows":mx["rows"],
            "reference_chart":mx["reference_chart"],
            "fifth_house_lord":mx["fifth_house_lord"],
            "eleventh_house_lord":mx["eleventh_house_lord"],
            "authority_common_sessions":ax["common_authority"]["session_count"],
            "authority_range":[ax["common_authority"]["first_date"],ax["common_authority"]["last_date"]],
            "targets":cfg["authority"]["targets"],
            "states":cfg["states"],"horizons":cfg["horizons"],"predictions":cfg["predictions"],
            "production_authority_effect":False
        },indent=2)); return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    features={r["date"]:r for r in load_csv(ROOT/cfg["feature_registry"])}
    results=[]; pvals=[]; rng=random.Random(RNG_SEED)

    for target,tmeta in cfg["authority"]["targets"].items():
        rows=load_csv(ROOT/tmeta["file"])
        dates=[date.fromisoformat(r["date"]) for r in rows]
        close=[float(r["close"]) for r in rows]
        dret=returns(close)

        for h in cfg["horizons"]:
            vectors={i:vector(close,dret,i,h) for i in range(len(rows)-h)}
            for state in cfg["states"]:
                labels={i:as_bool(features[rows[i]["date"]][state]) for i in vectors if rows[i]["date"] in features}
                for outcome,pred in cfg["predictions"].items():
                    vals={i:vectors[i][outcome] for i in labels if vectors[i][outcome] is not None}
                    eligible=sorted(vals)
                    event=[i for i in eligible if labels[i]]
                    if not event: continue
                    em=mean(vals[i] for i in event)
                    comp=[vals[i] for i in eligible if not labels[i]]
                    inc=em-mean(comp) if comp else None
                    incm=matched(event,eligible,vals,dates)
                    p=empirical_p(em,circular_null(labels,eligible,vals,rng,cfg["circular_shifts"]))
                    key=f"{target}|{state}|{h}|{outcome}"
                    pvals.append((key,p))
                    results.append({
                        "key":key,"target":target,"research_instrument":tmeta["instrument"],
                        "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
                        "state":state,"horizon_sessions":h,"outcome":outcome,"prediction":pred,
                        "event_n":len(event),"event_mean":em,
                        "incremental_vs_complement":inc,
                        "incremental_vs_weekday_month":incm,
                        "circular_empirical_p":p,
                        "era_stats":era_stats(event,eligible,vals,dates,cfg["frozen_eras"])
                    })

    qmap=bh(pvals)
    supported=0
    for r in results:
        r["bh_q"]=qmap.get(r["key"],1.0)
        inc=r["incremental_vs_complement"]; incm=r["incremental_vs_weekday_month"]
        era_incs=[e["incremental_vs_complement"] for e in r["era_stats"] if e["incremental_vs_complement"] is not None]
        s=direction(inc)
        same=sum(1 for x in era_incs if direction(x)==s and s!=0)
        pred=r["prediction"]
        if pred=="POSITIVE":
            directional=inc is not None and inc>0
        elif pred=="MORE_NEGATIVE":
            directional=inc is not None and inc<0
        else:
            directional=False
        gate={
            "sample_size":r["event_n"]>=cfg["minimum_event_sessions"],
            "bh_q_le_0_05":r["bh_q"]<=0.05,
            "directional_prediction_satisfied":directional,
            "matched_control_direction_consistency":incm is not None and direction(inc)==direction(incm) and direction(inc)!=0,
            "at_least_3_eligible_eras":len(era_incs)>=cfg["era_stability"]["minimum_eligible_eras"],
            "at_least_3_same_direction_eras":same>=cfg["era_stability"]["minimum_same_direction_eras"]
        }
        r["research_gate"]=gate
        r["status"]="LONG_HISTORY_RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        supported += r["status"]=="LONG_HISTORY_RESEARCH_SUPPORTED_CANDIDATE"

    out={
        "version":cfg["version"],"status":"READY",
        "reference_chart":mx["reference_chart"],
        "house_lords":{"fifth":mx["fifth_house_lord"],"eleventh":mx["eleventh_house_lord"]},
        "authority":{
            "common_start":ax["common_authority"]["first_date"],
            "common_end":ax["common_authority"]["last_date"],
            "common_sessions":ax["common_authority"]["session_count"],
            "targets":cfg["authority"]["targets"]
        },
        "result_count":len(results),
        "long_history_research_supported_candidate_count":supported,
        "results":results,
        "governance":{
            "h3_preregistered":True,
            "factor_combinations":False,
            "posthoc_orb_search":False,
            "proxy_only_survivor_may_not_advance":True,
            "canonical_recent_confirmation_required":True,
            "database_writes":False,
            "production_authority_effect":False
        },
        "next_step":"BUILD_M77_16_4_H3_CANONICAL_RECENT_CONFIRMATION_ONLY_FOR_SURVIVORS" if supported else "H3_UNSUPPORTED_CLOSE_M77_16_VEDIC_PREDICTIVE_HYPOTHESES_II",
        "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps({
        "version":cfg["version"],"status":"READY",
        "authority_common_sessions":out["authority"]["common_sessions"],
        "authority_range":[out["authority"]["common_start"],out["authority"]["common_end"]],
        "result_count":len(results),
        "long_history_research_supported_candidate_count":supported,
        "next_step":out["next_step"],
        "production_authority_effect":False
    },indent=2))

if __name__=="__main__": main()
