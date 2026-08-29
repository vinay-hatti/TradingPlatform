#!/usr/bin/env python3
"""
M77.19.7.4.5 — Bearish Extreme-Outcome, Corporate-Action &
Robust-Economics Forensics

Research-only continuation of M77.19.7.4.4.

Goals:
- determine whether severe bearish negative economics are broad-based or tail-driven;
- compute robust descriptive statistics without deleting or altering authority data;
- quantify adverse-outcome tail frequencies;
- rank largest adverse historical observations with base/target price provenance;
- inspect frozen Polygon daily bars for large single-session price discontinuities;
- slice evidence by era, base-price band, native bearish class and predeclared
  high-risk component states.

Important:
A price discontinuity is DIAGNOSTIC ONLY. It is not automatically classified as
a stock split, reverse split, merger, acquisition or bad print.

No production model changes, fitting, threshold search, observation removal,
winsorization of authority data, or automatic bearish inversion are authorized.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.5-BEARISH-EXTREME-OUTCOME-CORPORATE-ACTION-ROBUST-ECONOMICS-FORENSICS-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_REPLAY_VERSION="M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
EXPECTED_OUTCOME_VERSION="M77.19.7.4.1.2-REPAIRED-FULL-PROFILE-AUTHORITY-REPIN-1.0"
EXPECTED_SYMBOLS=602
EXPECTED_PROFILES=556283
FIXED_HORIZONS=(5,10,20)
BEARISH_CLASSES=("BEARISH","STRONG_BEARISH")
TRIM_LEVELS=(0.01,0.025,0.05)
WINSOR_LEVELS=(0.01,0.025,0.05)
ADVERSE_THRESHOLDS=(0.10,0.20,0.50,1.00)
PERCENTILES=(0.01,0.05,0.10,0.25,0.50,0.75,0.90,0.95,0.99)
DISCONTINUITY_THRESHOLDS=(0.20,0.35,0.50,1.00)
FIXED_ERAS=(
    ("2003-2007",2003,2007),("2008-2012",2008,2012),("2013-2017",2013,2017),
    ("2018-2022",2018,2022),("2023-2026",2023,2026),
)
PRICE_BANDS=((0,5,"LT_5"),(5,20,"5_20"),(20,50,"20_50"),(50,100,"50_100"),
             (100,250,"100_250"),(250,float("inf"),"GE_250"))

# Predeclared from M77.19.7.4.4 findings. This is not selected dynamically by
# 7.4.5 outcomes and cannot promote a production semantic.
FOCUS_STATES=(
    ("decision_intelligence.decision","ELIGIBLE"),
    ("participation.state","CAPITULATION"),
    ("breakout.state","BREAKDOWN_CONFIRMED"),
    ("breakout.state","BREAKDOWN_SETUP"),
    ("alignment_score","80-100"),
    ("timeframe_states.1d.direction","STRONG_BEARISH"),
    ("timeframe_states.1w.direction","STRONG_BEARISH"),
    ("timeframe_states.1mo.direction","STRONG_BEARISH"),
)

class ForensicError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve_project_path(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists(): return p
    for anchor in ("research_data","reports","data"):
        if anchor in p.parts:
            q=root.joinpath(*p.parts[p.parts.index(anchor):])
            if q.exists(): return q
    if not p.is_absolute():
        q=root/p
        if q.exists():return q
    return p

def read_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ForensicError(f"{path}:{i}: invalid JSONL") from exc

def native_profile(row:Mapping[str,Any])->dict[str,Any]|None:
    status=row.get("status")
    if status=="NOT_ELIGIBLE_NATIVE": return None
    if status!="REPLAYED": raise ForensicError(f"unexpected replay status {status!r}")
    p=row.get("profile")
    if not isinstance(p,dict) or "direction" not in p or "timeframe_states" not in p:
        raise ForensicError("REPLAYED row missing M77.19.7.3.1.1 full profile")
    return p

def get_path(obj:Any,path:str)->Any:
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def canonical_state(v:Any)->str:
    if v is None:return "MISSING"
    if isinstance(v,bool):return "TRUE" if v else "FALSE"
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        x=float(v)
        if math.isfinite(x) and 0<=x<=100:
            if x<20:return "0-20"
            if x<40:return "20-40"
            if x<60:return "40-60"
            if x<80:return "60-80"
            return "80-100"
        return f"NUMERIC:{round(x,6)}"
    s=str(v).strip().upper()
    return s or "EMPTY"

def era_label(year:int)->str:
    for label,a,b in FIXED_ERAS:
        if a<=year<=b:return label
    return "OUTSIDE_FIXED_ERAS"

def price_band(x:float)->str:
    for lo,hi,label in PRICE_BANDS:
        if lo<=x<hi:return label
    raise ForensicError(f"unbinnable base price {x}")

def percentile_sorted(xs:list[float],q:float)->float|None:
    if not xs:return None
    if len(xs)==1:return xs[0]
    pos=(len(xs)-1)*q
    lo=int(math.floor(pos));hi=int(math.ceil(pos))
    if lo==hi:return xs[lo]
    return xs[lo]+(xs[hi]-xs[lo])*(pos-lo)

def trimmed_mean(xs:list[float],alpha:float)->float|None:
    if not xs:return None
    ys=sorted(xs);k=int(math.floor(len(ys)*alpha))
    if 2*k>=len(ys):return None
    z=ys[k:len(ys)-k] if k else ys
    return statistics.fmean(z) if z else None

def winsorized_mean(xs:list[float],alpha:float)->float|None:
    if not xs:return None
    ys=sorted(xs);k=int(math.floor(len(ys)*alpha))
    if k==0:return statistics.fmean(ys)
    if 2*k>=len(ys):return None
    lo=ys[k];hi=ys[-k-1]
    z=[lo]*k+ys[k:len(ys)-k]+[hi]*k
    return statistics.fmean(z)

def robust_stats(xs:list[float])->dict[str,Any]:
    ys=sorted(xs)
    out={
        "count":len(ys),
        "mean":statistics.fmean(ys) if ys else None,
        "median":statistics.median(ys) if ys else None,
        "min":ys[0] if ys else None,
        "max":ys[-1] if ys else None,
        "positive_count":sum(x>0 for x in ys),
        "nonpositive_count":sum(x<=0 for x in ys),
    }
    out["accuracy"]=out["positive_count"]/len(ys) if ys else None
    out["percentiles"]={f"p{int(q*100):02d}":percentile_sorted(ys,q) for q in PERCENTILES}
    out["trimmed_means"]={f"{100*a:g}pct":trimmed_mean(ys,a) for a in TRIM_LEVELS}
    out["winsorized_means"]={f"{100*a:g}pct":winsorized_mean(ys,a) for a in WINSOR_LEVELS}
    out["adverse_tail_counts"]={
        f"underlying_up_gt_{int(t*100)}pct":sum(x<=-t for x in ys)
        for t in ADVERSE_THRESHOLDS
    }
    out["adverse_tail_rates"]={
        k:(v/len(ys) if ys else None) for k,v in out["adverse_tail_counts"].items()
    }
    return out

def read_daily(path:Path)->tuple[list[dt.date],list[float]]:
    dates=[];closes=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        if not {"session_date","close"}.issubset(set(r.fieldnames or [])):
            raise ForensicError(f"{path}: session_date/close missing")
        for row in r:
            d=dt.date.fromisoformat(row["session_date"]);c=float(row["close"])
            if not math.isfinite(c) or c<=0:raise ForensicError(f"{path}:{d}: invalid close")
            dates.append(d);closes.append(c)
    if dates!=sorted(dates) or len(dates)!=len(set(dates)):
        raise ForensicError(f"{path}: dates not unique ascending")
    return dates,closes

def resolve_source(root:Path,om:Mapping[str,Any],rm:Mapping[str,Any])->Path:
    if om.get("source_data_sha256")!=rm.get("source_data_sha256"):
        raise ForensicError(f"{om.get('symbol')}: source SHA mismatch")
    p=resolve_project_path(root,rm.get("source_data_file") or "")
    if not p.is_file():raise ForensicError(f"{om.get('symbol')}: frozen source missing")
    if sha256_file(p)!=rm.get("source_data_sha256"):
        raise ForensicError(f"{om.get('symbol')}: frozen source file SHA mismatch")
    return p

def horizon_discontinuity(dates:list[dt.date],closes:list[float],base:str,target:str)->dict[str,Any]:
    idx={d:i for i,d in enumerate(dates)}
    bd=dt.date.fromisoformat(base);td=dt.date.fromisoformat(target)
    if bd not in idx or td not in idx:return {"status":"DATE_NOT_FOUND"}
    a=idx[bd];b=idx[td]
    if b<=a:return {"status":"INVALID_WINDOW"}
    events=[]
    for i in range(a+1,b+1):
        ret=closes[i]/closes[i-1]-1
        events.append((abs(ret),ret,dates[i-1],dates[i],closes[i-1],closes[i]))
    if not events:return {"status":"NO_TRANSITIONS"}
    events.sort(reverse=True,key=lambda x:x[0])
    _,ret,d0,d1,c0,c1=events[0]
    ratio=max(c0,c1)/min(c0,c1)
    # Diagnostic proximity to common integer/reciprocal split ratios.
    common=(2,3,4,5,10,20)
    nearest=min(common,key=lambda k:abs(ratio-k))
    ratio_distance=abs(ratio-nearest)/nearest
    return {
        "status":"OK","max_abs_single_session_return":abs(ret),
        "signed_single_session_return":ret,
        "from_date":d0.isoformat(),"to_date":d1.isoformat(),
        "from_close":c0,"to_close":c1,"price_ratio":ratio,
        "nearest_common_split_ratio":nearest,
        "relative_distance_to_common_split_ratio":ratio_distance,
        "common_split_ratio_suspect":abs(ret)>=0.35 and ratio_distance<=0.03,
    }

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--component-authority-json",default="reports/m77_19_7_4_4_bearish_signal_root_cause_component_attribution_counterfactual_forensics.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_5_bearish_extreme_outcome_corporate_action_robust_economics_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_5_extreme_adverse_observations.csv")
    ap.add_argument("--top-extremes",type=int,default=100)
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    op=resolve_project_path(root,args.outcome_authority_json)
    rp=resolve_project_path(root,args.replay_authority_json)
    cp=resolve_project_path(root,args.component_authority_json)

    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise ForensicError("outcome authority SHA mismatch")
    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:raise ForensicError("replay authority SHA mismatch")
    outcome=load_json(op);replay=load_json(rp)
    if outcome.get("version")!=EXPECTED_OUTCOME_VERSION:raise ForensicError("outcome authority version mismatch")
    if replay.get("version")!=EXPECTED_REPLAY_VERSION:raise ForensicError("replay authority version mismatch")
    if outcome.get("status")!="READY" or replay.get("status")!="READY":raise ForensicError("upstream authority not READY")
    if outcome.get("successful_symbol_evaluation_count")!=EXPECTED_SYMBOLS:raise ForensicError("outcome symbol count mismatch")
    if replay.get("successful_symbol_cadence_replay_count")!=EXPECTED_SYMBOLS:raise ForensicError("replay symbol count mismatch")

    # M77.19.7.4.4 is semantic evidence authority, SHA recorded diagnostically
    # because the current report was generated after the package was built.
    component=load_json(cp)
    if component.get("status")!="READY":raise ForensicError("7.4.4 component authority not READY")
    if component.get("successful_symbol_count")!=EXPECTED_SYMBOLS:raise ForensicError("7.4.4 symbol count mismatch")
    if component.get("bearish_observation_count")!=145720:raise ForensicError("7.4.4 bearish observation authority mismatch")

    rms={str(x["symbol"]):x for x in replay.get("symbols") or [] if x.get("cadence")=="WEEKLY"}
    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    if len(rms)!=EXPECTED_SYMBOLS or len(oms)!=EXPECTED_SYMBOLS:raise ForensicError("symbol authority cardinality mismatch")

    groups=defaultdict(lambda:defaultdict(list))
    extremes=[]
    discontinuity_counts=defaultdict(lambda:defaultdict(int))
    eval_count=0

    for symbol in sorted(oms):
        om=oms[symbol];rm=rms[symbol]
        source=resolve_source(root,om,rm)
        dates,closes=read_daily(source)

        profile_file=resolve_project_path(root,rm["result_file"])
        if sha256_file(profile_file)!=rm["result_sha256"]:raise ForensicError(f"{symbol}: replay result SHA mismatch")
        profiles={}
        for row in read_jsonl(profile_file):
            p=native_profile(row)
            if p is not None:profiles[str(row["as_of"])[:10]]=p

        outcome_file=resolve_project_path(root,om["outcome_file"])
        if sha256_file(outcome_file)!=om["outcome_sha256"]:raise ForensicError(f"{symbol}: outcome SHA mismatch")
        for row in read_jsonl(outcome_file):
            native=str(row.get("native_direction") or row.get("direction") or "").upper()
            if native not in BEARISH_CLASSES:continue
            as_of=str(row["as_of"])[:10]
            profile=profiles.get(as_of)
            if profile is None:raise ForensicError(f"{symbol} {as_of}: bearish profile join missing")
            if str(profile.get("direction") or "").upper()!=native:raise ForensicError(f"{symbol} {as_of}: direction mismatch")
            era=era_label(dt.date.fromisoformat(as_of).year)
            for h in FIXED_HORIZONS:
                o=row["outcomes"][str(h)]
                if o.get("status")!="MATURED":continue
                eval_count+=1
                fwd=float(o["forward_return"]);dret=-fwd
                base=float(o["base_close"]);target=float(o["target_close"])
                keys=[
                    "ALL_BEARISH",
                    f"CLASS::{native}",
                    f"ERA::{era}",
                    f"PRICE_BAND::{price_band(base)}",
                ]
                for path,state in FOCUS_STATES:
                    if canonical_state(get_path(profile,path))==state:
                        keys.append(f"FOCUS::{path}::{state}")
                disc=horizon_discontinuity(dates,closes,o["base_date"],o["target_date"])
                for key in keys:
                    groups[key][h].append(dret)
                    if disc.get("status")=="OK":
                        for t in DISCONTINUITY_THRESHOLDS:
                            if disc["max_abs_single_session_return"]>=t:
                                discontinuity_counts[(key,h)][f"ge_{int(t*100)}pct"]+=1
                        if disc.get("common_split_ratio_suspect"):
                            discontinuity_counts[(key,h)]["common_split_ratio_suspect"]+=1
                if dret<=-0.10:
                    extremes.append({
                        "symbol":symbol,"as_of":as_of,"horizon_sessions":h,
                        "native_direction":native,"base_date":o["base_date"],
                        "target_date":o["target_date"],"base_close":base,"target_close":target,
                        "forward_return":fwd,"bearish_directional_return":dret,
                        "era":era,"base_price_band":price_band(base),
                        "decision":canonical_state(get_path(profile,"decision_intelligence.decision")),
                        "participation_state":canonical_state(get_path(profile,"participation.state")),
                        "breakout_state":canonical_state(get_path(profile,"breakout.state")),
                        "alignment_score_bin":canonical_state(get_path(profile,"alignment_score")),
                        "direction_1d":canonical_state(get_path(profile,"timeframe_states.1d.direction")),
                        "direction_1w":canonical_state(get_path(profile,"timeframe_states.1w.direction")),
                        "direction_1mo":canonical_state(get_path(profile,"timeframe_states.1mo.direction")),
                        **{f"discontinuity_{k}":v for k,v in disc.items()},
                    })

    summaries={}
    for key,hmap in sorted(groups.items()):
        summaries[key]={}
        for h in FIXED_HORIZONS:
            s=robust_stats(hmap.get(h,[]))
            dcounts=dict(discontinuity_counts.get((key,h),{}))
            s["price_discontinuity_counts"]=dcounts
            s["price_discontinuity_rates"]={
                k:(v/s["count"] if s["count"] else None) for k,v in dcounts.items()
            }
            summaries[key][str(h)]=s

    extremes.sort(key=lambda x:x["bearish_directional_return"])
    top_extremes=extremes[:max(1,args.top_extremes)]

    # Tail contribution diagnostic: how much the worst 1/2.5/5% influence mean.
    tail_contribution={}
    for h in FIXED_HORIZONS:
        xs=sorted(groups["ALL_BEARISH"][h])
        baseline=statistics.fmean(xs)
        tail_contribution[str(h)]={}
        for a in TRIM_LEVELS:
            k=int(math.floor(len(xs)*a))
            central=xs[k:len(xs)-k] if k else xs
            tail_contribution[str(h)][f"{100*a:g}pct_trim"]={
                "raw_mean":baseline,
                "trimmed_mean":statistics.fmean(central),
                "mean_change_after_trim":statistics.fmean(central)-baseline,
                "tail_observation_count_each_side":k,
            }

    report={
        "version":VERSION,"status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "component_authority_sha256":sha256_file(cp),
        "component_authority_bearish_observation_count":145720,
        "successful_symbol_count":EXPECTED_SYMBOLS,
        "aggregate_matured_bearish_horizon_observation_count":eval_count,
        "fixed_horizons_sessions":list(FIXED_HORIZONS),
        "focus_states":[{"path":p,"state":s} for p,s in FOCUS_STATES],
        "robust_economics":summaries,
        "tail_contribution_diagnostics":tail_contribution,
        "largest_adverse_observations":top_extremes,
        "governance":{
            "polygon_api_queried":False,"database_access":"NONE","price_history_table_used":False,
            "frozen_polygon_materialization_used":True,
            "profile_recomputation_performed":False,
            "observations_removed_from_authority":False,
            "authority_returns_winsorized":False,
            "winsorization_used_for_diagnostic_mean_only":True,
            "trimmed_mean_used_for_diagnostic_only":True,
            "corporate_action_auto_classification":False,
            "price_discontinuity_is_diagnostic_only":True,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,"classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_authority_effect":False,"production_model_change_authorized":False,
        },
        "decision_gate":{
            "bearish_tail_artifact_review_complete":True,
            "bearish_semantic_change_authorized":False,
            "next_step":"REVIEW_M77_19_7_4_5_ROBUST_ECONOMICS_AND_DISCONTINUITIES_BEFORE_CAUSAL_INTERVENTION",
        },
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(top_extremes[0].keys()) if top_extremes else [
        "symbol","as_of","horizon_sessions","native_direction","base_date","target_date",
        "base_close","target_close","forward_return","bearish_directional_return"
    ]
    with outc.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore");w.writeheader()
        for r in top_extremes:w.writerow(r)

    print("=== M77.19.7.4.5 BEARISH EXTREME-OUTCOME, CORPORATE-ACTION & ROBUST-ECONOMICS FORENSICS ===")
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOLS}")
    print(f"component_authority_sha256: {sha256_file(cp)}")
    for h in FIXED_HORIZONS:
        s=summaries["ALL_BEARISH"][str(h)]
        print(f"horizon_{h}_all_bearish: mean={s['mean']} median={s['median']} "
              f"trim1={s['trimmed_means']['1pct']} trim2.5={s['trimmed_means']['2.5pct']} "
              f"trim5={s['trimmed_means']['5pct']} win1={s['winsorized_means']['1pct']} "
              f"p01={s['percentiles']['p01']} p99={s['percentiles']['p99']}")
        print(f"horizon_{h}_adverse_tail_rates: {s['adverse_tail_rates']}")
        print(f"horizon_{h}_price_discontinuity_rates: {s['price_discontinuity_rates']}")
        for p,state in FOCUS_STATES[:4]:
            k=f"FOCUS::{p}::{state}"
            x=summaries.get(k,{}).get(str(h))
            if x:
                print(f"horizon_{h}_{p}_{state}: count={x['count']} mean={x['mean']} "
                      f"median={x['median']} trim5={x['trimmed_means']['5pct']} "
                      f"win5={x['winsorized_means']['5pct']}")
    print(f"largest_adverse_observation_count_reported: {len(top_extremes)}")
    print("corporate_action_auto_classification: False")
    print("observations_removed_from_authority: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_5_ROBUST_ECONOMICS_AND_DISCONTINUITIES_BEFORE_CAUSAL_INTERVENTION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
