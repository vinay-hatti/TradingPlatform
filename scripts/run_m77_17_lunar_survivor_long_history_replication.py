#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,math,random
from datetime import date
from pathlib import Path
from statistics import mean
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_17_lunar_survivor_long_history_replication.json"
OUT=ROOT/"reports/m77/m77_17_lunar_survivor_long_history_replication.json"
CLOSURE=ROOT/"reports/m77/m77_17_vedic_research_closure.json"
CONFIRM="RUN_M77_17_LUNAR_SURVIVOR_LONG_HISTORY_REPLICATION"
RNG_SEED=771700
ITER=10000

def load_csv(p):
    with Path(p).open() as f:
        return list(csv.DictReader(f))

def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n")
    json.loads(t.read_text())
    t.replace(p)

def find_lunar_registry(cfg):
    candidates=[cfg["lunar_survivor"]["lunar_feature_source"]]+cfg["lunar_survivor"]["fallback_lunar_registry_candidates"]
    for rel in candidates:
        p=ROOT/rel
        if p.exists():
            return p
    raise SystemExit("M77.17 blocked: no lunar registry found from approved frozen candidates")

def phase_active(row,center,half):
    # Prefer explicit frozen event-state fields if they exist.
    for k in ("first_quarter_window","FIRST_QUARTER_WINDOW","event_active"):
        if k in row and str(row[k]).strip()!="":
            v=str(row[k]).strip().lower()
            if v in ("1","true","t","yes","y"): return True
            if v in ("0","false","f","no","n"): return False
    # Otherwise derive strictly from frozen lunar phase angle.
    for k in ("lunar_phase_angle_deg","moon_phase_angle_deg","phase_angle_deg"):
        if k in row and str(row[k]).strip()!="":
            a=float(row[k])%360.0
            d=abs(a-center)
            d=min(d,360.0-d)
            return d<=half
    # Certified Panchanga registry fallback: phase = Moon - Sun, modulo 360.
    if row.get("moon_sidereal_deg") not in (None,"") and row.get("sun_sidereal_deg") not in (None,""):
        a=(float(row["moon_sidereal_deg"])-float(row["sun_sidereal_deg"]))%360.0
        d=abs(a-center); d=min(d,360.0-d)
        return d<=half
    raise KeyError("no explicit first-quarter state, lunar phase angle, or certified Sun/Moon longitude pair found")

def matched_control(event_idx,eligible,vals,dates):
    ev=set(event_idx); diffs=[]
    for i in event_idx:
        c=[j for j in eligible if j not in ev and dates[j].weekday()==dates[i].weekday() and dates[j].month==dates[i].month]
        if c:
            diffs.append(vals[i]-mean(vals[j] for j in c))
    return mean(diffs) if diffs else None

def cluster_events(event_idx):
    if not event_idx:return []
    clusters=[]; cur=[event_idx[0]]
    for i in event_idx[1:]:
        if i==cur[-1]+1: cur.append(i)
        else: clusters.append(cur); cur=[i]
    clusters.append(cur)
    return clusters

def bootstrap_incremental(event_idx,eligible,vals,rng,iters):
    evset=set(event_idx)
    comp=[i for i in eligible if i not in evset]
    clusters=cluster_events(event_idx)
    if not clusters or not comp:return []
    out=[]
    for _ in range(iters):
        sampled=[]
        while len(sampled)<len(event_idx):
            sampled.extend(rng.choice(clusters))
        sampled=sampled[:len(event_idx)]
        e=mean(vals[i] for i in sampled)
        c=mean(vals[i] for i in rng.choices(comp,k=len(comp)))
        out.append(e-c)
    return out

def circular_year_stratified(event_idx,eligible,vals,dates,rng,iters):
    by_year={}
    elig_by_year={}
    for i in eligible:
        elig_by_year.setdefault(dates[i].year,[]).append(i)
    for i in event_idx:
        by_year.setdefault(dates[i].year,[]).append(i)
    obs=mean(vals[i] for i in event_idx)
    null=[]
    years=sorted(by_year)
    for _ in range(iters):
        shifted=[]
        for y in years:
            elig=elig_by_year.get(y,[])
            ev=by_year.get(y,[])
            if not elig or not ev: continue
            pos={idx:k for k,idx in enumerate(elig)}
            base=[pos[i] for i in ev if i in pos]
            if not base: continue
            sh=rng.randrange(1,len(elig)) if len(elig)>1 else 0
            shifted.extend(elig[(k+sh)%len(elig)] for k in base)
        if shifted:
            null.append(mean(vals[i] for i in shifted))
    if not null:return 1.0,None
    c=mean(null); d=abs(obs-c)
    p=(1+sum(abs(x-c)>=d for x in null))/(len(null)+1)
    return p,c

def era_stats(event_idx,eligible,vals,dates,eras):
    ev=set(event_idx); out=[]
    for a,b in eras:
        ei=[i for i in event_idx if a<=dates[i].isoformat()<=b]
        ci=[i for i in eligible if i not in ev and a<=dates[i].isoformat()<=b]
        inc=None if not ei or not ci else mean(vals[i] for i in ei)-mean(vals[i] for i in ci)
        out.append({"era":[a,b],"event_n":len(ei),"incremental_vs_complement":inc})
    return out

def nonoverlap(event_idx,horizon):
    out=[]; last=-10**9
    for i in event_idx:
        if i-last>=horizon:
            out.append(i); last=i
    return out

def run_target(target,meta,lunar,phase_cfg,eras,accept):
    rows=load_csv(ROOT/meta["file"])
    dates=[date.fromisoformat(r["date"]) for r in rows]
    close=[float(r["close"]) for r in rows]
    bydate={r["date"]:i for i,r in enumerate(rows)}
    h=10
    vals={}
    event=[]
    for i in range(len(rows)-h):
        vals[i]=abs(close[i+h]/close[i]-1)
        lr=lunar.get(rows[i]["date"])
        if lr and phase_active(lr,phase_cfg["phase_angle_center_deg"],phase_cfg["half_width_deg"]):
            event.append(i)
    eligible=sorted(vals)
    evset=set(event)
    comp=[i for i in eligible if i not in evset]
    if not event or not comp:
        raise SystemExit(f"M77.17 blocked: insufficient event/complement rows for {target}")
    event_mean=mean(vals[i] for i in event)
    comp_mean=mean(vals[i] for i in comp)
    inc=event_mean-comp_mean
    matched=matched_control(event,eligible,vals,dates)

    rng=random.Random(RNG_SEED+sum(map(ord,target)))
    p,null_mean=circular_year_stratified(event,eligible,vals,dates,rng,ITER)
    boots=bootstrap_incremental(event,eligible,vals,rng,ITER)
    ci=[float(np.quantile(boots,0.025)),float(np.quantile(boots,0.975))] if boots else [None,None]
    non=nonoverlap(event,h)
    non_comp=[i for i in eligible if i not in set(non)]
    non_inc=mean(vals[i] for i in non)-mean(vals[i] for i in non_comp) if non and non_comp else None
    eras_out=era_stats(event,eligible,vals,dates,eras)
    era_incs=[e["incremental_vs_complement"] for e in eras_out if e["incremental_vs_complement"] is not None]
    supportive=sum(1 for x in era_incs if x<0)

    gates={
        "negative_incremental":inc<0,
        "dependence_robust_empirical_p_le_0_05":p<=accept["dependence_robust_empirical_p_le"],
        "bootstrap_ci_excludes_zero_negative":ci[1] is not None and ci[1]<0,
        "at_least_3_eligible_eras":len(era_incs)>=accept["minimum_eligible_eras"],
        "at_least_3_same_direction_eras":supportive>=accept["minimum_same_direction_eras"],
        "nonoverlap_same_direction":non_inc is not None and non_inc<0,
        "weekday_month_control_same_direction":matched is not None and matched<0,
        "economic_effect_abs_ge_min":abs(inc)>=accept["economic_effect_abs_min"]
    }
    return {
        "target":target,
        "instrument":meta["instrument"],
        "event_n":len(event),
        "event_mean_absolute_return":event_mean,
        "complement_mean_absolute_return":comp_mean,
        "incremental_vs_complement":inc,
        "incremental_vs_weekday_month":matched,
        "dependence_robust_empirical_p":p,
        "dependence_robust_null_mean":null_mean,
        "bootstrap_ci95":ci,
        "nonoverlap_event_n":len(non),
        "nonoverlap_incremental":non_inc,
        "era_stats":eras_out,
        "gates":gates,
        "replication_pass":all(gates.values())
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run","closure"))
    ap.add_argument("--confirm")
    a=ap.parse_args()
    cfg=json.loads(CFG.read_text())
    auth=ROOT/cfg["lunar_survivor"]["long_history_authority"]["certification"]
    if not auth.exists():
        raise SystemExit("M77.17 blocked: long-history authority certification missing")
    ax=json.loads(auth.read_text())
    if not ax.get("certified_for_m77_15_7_long_history_replication"):
        raise SystemExit("M77.17 blocked: long-history authority not certified")
    if ax["common_authority"]["session_count"]<cfg["lunar_survivor"]["long_history_authority"]["expected_sessions"]:
        raise SystemExit("M77.17 blocked: certified common-session count below frozen expected authority")

    if a.mode=="closure":
        closure={
          "version":"M77.17-VEDIC-RESEARCH-CLOSURE-1.0",
          "status":"READY",
          "M77_15":cfg["closure"]["M77_15"],
          "M77_16":cfg["closure"]["M77_16"],
          "production_authority_effect":False
        }
        write_json_atomic(CLOSURE,closure)
        print(json.dumps(closure,indent=2)); return

    lunar_path=find_lunar_registry(cfg)
    if a.mode=="preflight":
        print(json.dumps({
          "version":cfg["version"],"status":"READY","confirmation_required":CONFIRM,
          "lunar_registry":str(lunar_path),
          "frozen_survivor":cfg["lunar_survivor"]["source_hypothesis"],
          "authority_common_sessions":ax["common_authority"]["session_count"],
          "authority_range":[ax["common_authority"]["first_date"],ax["common_authority"]["last_date"]],
          "primary_replication":cfg["lunar_survivor"]["primary_replication"],
          "secondary_generalization":cfg["lunar_survivor"]["secondary_generalization"],
          "acceptance":cfg["lunar_survivor"]["acceptance"],
          "decision_policy":cfg["lunar_survivor"]["decision_policy"],
          "production_authority_effect":False
        },indent=2)); return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    lunar={r["date"]:r for r in load_csv(lunar_path)}
    files=cfg["lunar_survivor"]["long_history_authority"]["files"]
    metas={
      "SPX":{"instrument":"SPY","file":files["SPX"]},
      "NDX":{"instrument":"QQQ_LINEAGE","file":files["NDX"]},
      "RUT":{"instrument":"IWM","file":files["RUT"]}
    }
    results={t:run_target(t,metas[t],lunar,cfg["lunar_survivor"]["event_definition"],
                          cfg["lunar_survivor"]["frozen_eras"],cfg["lunar_survivor"]["acceptance"])
             for t in ("NDX","SPX","RUT")}

    primary=results["NDX"]
    secondary_pass_all=results["SPX"]["replication_pass"] and results["RUT"]["replication_pass"]
    if not primary["replication_pass"]:
        disposition="TERMINATE_M77_14_PROSPECTIVE_SHADOW_AND_CLOSE_LUNAR_RESEARCH"
    elif secondary_pass_all:
        disposition="CONTINUE_PROSPECTIVE_SHADOW_WITH_STRONGER_CREDIBILITY"
    else:
        disposition="CONTINUE_NDX_SPECIFIC_PROSPECTIVE_SHADOW"

    out={
      "version":cfg["version"],"status":"READY",
      "lunar_registry":str(lunar_path),
      "frozen_survivor":cfg["lunar_survivor"]["source_hypothesis"],
      "authority":{
        "common_start":ax["common_authority"]["first_date"],
        "common_end":ax["common_authority"]["last_date"],
        "common_sessions":ax["common_authority"]["session_count"]
      },
      "primary_replication_target":"NDX",
      "results":results,
      "primary_replication_pass":primary["replication_pass"],
      "all_three_same_framework_pass":all(r["replication_pass"] for r in results.values()),
      "disposition":disposition,
      "prospective_shadow_policy":{
        "automatic_stop_action":False,
        "automatic_production_promotion":False,
        "human_review_required":True
      },
      "database_writes":False,
      "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps({
      "version":cfg["version"],"status":"READY",
      "authority_common_sessions":out["authority"]["common_sessions"],
      "authority_range":[out["authority"]["common_start"],out["authority"]["common_end"]],
      "primary_replication_pass":out["primary_replication_pass"],
      "all_three_same_framework_pass":out["all_three_same_framework_pass"],
      "disposition":out["disposition"],
      "summary":{k:{
        "instrument":v["instrument"],
        "event_n":v["event_n"],
        "incremental_vs_complement":v["incremental_vs_complement"],
        "p":v["dependence_robust_empirical_p"],
        "bootstrap_ci95":v["bootstrap_ci95"],
        "replication_pass":v["replication_pass"]
      } for k,v in results.items()},
      "production_authority_effect":False
    },indent=2))

if __name__=="__main__": main()
