#!/usr/bin/env python3
"""
M77.19.7.4.6 — Bearish Lifecycle / Exhaustion vs Continuation Causal Forensics

Research-only continuation of M77.19.7.4.5.

Primary causal question:
Does Stock Intelligence identify bearish states correctly but overinterpret
state maturity/severity as evidence of additional future downside?

Point-in-time lifecycle observables only:
- consecutive prior bearish WEEKLY replay observations
- current transition into bearish / strong-bearish
- prior 5/10/20 daily-session returns
- drawdown from prior 63-session high
- current breakout / participation states
- 1d / 1w / 1mo bearish direction alignment

No future bars are used to construct lifecycle features. Future bars are used
only for realized 5/10/20-session outcome labels already authorized by M77.19.7.4.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.6-BEARISH-LIFECYCLE-EXHAUSTION-CONTINUATION-CAUSAL-FORENSICS-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_REPLAY_VERSION="M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
EXPECTED_OUTCOME_VERSION="M77.19.7.4.1.2-REPAIRED-FULL-PROFILE-AUTHORITY-REPIN-1.0"
EXPECTED_SYMBOLS=602
FIXED_HORIZONS=(5,10,20)
BEARISH_CLASSES=("BEARISH","STRONG_BEARISH")
BULLISH_CLASSES=("BULLISH","STRONG_BULLISH")

# Predeclared lifecycle definitions. No search/optimization.
EARLY_MAX_STREAK=2
ESTABLISHED_MAX_STREAK=8
PERSISTENT_LATE_MIN_STREAK=9

# Fixed exhaustion overlays. These are descriptive, not selection thresholds.
PRIOR_20_DECLINE_THRESHOLD=-0.10
PRIOR_10_DECLINE_THRESHOLD=-0.07
DRAWDOWN_63_THRESHOLD=-0.15
STRONG_ALIGNMENT_MIN_COUNT=2

class ForensicError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():return p
    for anchor in ("research_data","reports","data"):
        if anchor in p.parts:
            q=root.joinpath(*p.parts[p.parts.index(anchor):])
            if q.exists():return q
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

def profile_from_row(row:Mapping[str,Any])->dict[str,Any]|None:
    status=row.get("status")
    if status=="NOT_ELIGIBLE_NATIVE":return None
    if status!="REPLAYED":raise ForensicError(f"unexpected replay status {status!r}")
    p=row.get("profile")
    if not isinstance(p,dict) or "direction" not in p or "timeframe_states" not in p:
        raise ForensicError("REPLAYED row missing exact full-profile authority")
    return p

def get_path(obj:Any,path:str)->Any:
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def read_daily(path:Path)->tuple[list[dt.date],list[float]]:
    dates=[];closes=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        if not {"session_date","close"}.issubset(set(r.fieldnames or [])):
            raise ForensicError(f"{path}: missing session_date/close")
        for row in r:
            d=dt.date.fromisoformat(row["session_date"]);c=float(row["close"])
            if not math.isfinite(c) or c<=0:raise ForensicError(f"{path}:{d}: invalid close")
            dates.append(d);closes.append(c)
    if dates!=sorted(dates) or len(dates)!=len(set(dates)):
        raise ForensicError(f"{path}: dates must be unique ascending")
    return dates,closes

def prior_return(dates:list[dt.date], closes:list[float], as_of:dt.date, sessions:int)->float|None:
    idx={d:i for i,d in enumerate(dates)}
    if as_of not in idx:return None
    i=idx[as_of]
    if i-sessions<0:return None
    return closes[i]/closes[i-sessions]-1.0

def drawdown_from_prior_high(dates:list[dt.date], closes:list[float], as_of:dt.date, lookback:int=63)->float|None:
    idx={d:i for i,d in enumerate(dates)}
    if as_of not in idx:return None
    i=idx[as_of]
    if i<=0:return None
    lo=max(0,i-lookback)
    prior=closes[lo:i]
    if not prior:return None
    high=max(prior)
    return closes[i]/high-1.0

def lifecycle_label(streak:int)->str:
    if streak<=EARLY_MAX_STREAK:return "EARLY_TRANSITION"
    if streak<=ESTABLISHED_MAX_STREAK:return "ESTABLISHED"
    return "PERSISTENT_LATE"

def strong_bearish_tf_count(profile:Mapping[str,Any])->int:
    n=0
    for tf in ("1d","1w","1mo"):
        d=str(get_path(profile,f"timeframe_states.{tf}.direction") or "").upper()
        if d=="STRONG_BEARISH":n+=1
    return n

def overlay_flags(profile:Mapping[str,Any], prior10:float|None, prior20:float|None, dd63:float|None)->dict[str,bool]:
    breakout=str(get_path(profile,"breakout.state") or "").upper()
    participation=str(get_path(profile,"participation.state") or "").upper()
    tfcount=strong_bearish_tf_count(profile)
    return {
        "PRIOR_20_DECLINE_GE_10PCT": prior20 is not None and prior20<=PRIOR_20_DECLINE_THRESHOLD,
        "PRIOR_10_DECLINE_GE_7PCT": prior10 is not None and prior10<=PRIOR_10_DECLINE_THRESHOLD,
        "DRAWDOWN_63_GE_15PCT": dd63 is not None and dd63<=DRAWDOWN_63_THRESHOLD,
        "BREAKDOWN_CONFIRMED": breakout=="BREAKDOWN_CONFIRMED",
        "CAPITULATION": participation=="CAPITULATION",
        "STRONG_BEARISH_ALIGNMENT_2PLUS": tfcount>=STRONG_ALIGNMENT_MIN_COUNT,
    }

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
        "p10":sorted(xs)[max(0,int(0.10*(len(xs)-1)))],
        "p90":sorted(xs)[min(len(xs)-1,int(0.90*(len(xs)-1)))],
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
    ap.add_argument("--robust-authority-json",default="reports/m77_19_7_4_5_bearish_extreme_outcome_corporate_action_robust_economics_forensics.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_6_bearish_lifecycle_exhaustion_vs_continuation_causal_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    op=resolve(root,args.outcome_authority_json);rp=resolve(root,args.replay_authority_json);bp=resolve(root,args.robust_authority_json)
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise ForensicError("outcome SHA mismatch")
    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:raise ForensicError("replay SHA mismatch")
    outcome=load_json(op);replay=load_json(rp);robust=load_json(bp)
    if outcome.get("version")!=EXPECTED_OUTCOME_VERSION:raise ForensicError("outcome version mismatch")
    if replay.get("version")!=EXPECTED_REPLAY_VERSION:raise ForensicError("replay version mismatch")
    if robust.get("status")!="READY":raise ForensicError("M77.19.7.4.5 robust authority not READY")
    if outcome.get("successful_symbol_evaluation_count")!=EXPECTED_SYMBOLS:raise ForensicError("outcome symbol count mismatch")
    if replay.get("successful_symbol_cadence_replay_count")!=EXPECTED_SYMBOLS:raise ForensicError("replay symbol count mismatch")

    rms={str(x["symbol"]):x for x in replay["symbols"] if x.get("cadence")=="WEEKLY"}
    oms={str(x["symbol"]):x for x in outcome["symbols"]}
    if len(rms)!=EXPECTED_SYMBOLS or len(oms)!=EXPECTED_SYMBOLS:raise ForensicError("symbol count mismatch")

    grouped=defaultdict(lambda:defaultdict(list))
    overlay_grouped=defaultdict(lambda:defaultdict(list))
    rows_out=[]
    transition_counts=defaultdict(int)

    for symbol in sorted(oms):
        om=oms[symbol];rm=rms[symbol]
        source=resolve(root,rm["source_data_file"])
        if sha256_file(source)!=rm["source_data_sha256"]:raise ForensicError(f"{symbol}: source SHA mismatch")
        dates,closes=read_daily(source)

        profile_file=resolve(root,rm["result_file"])
        if sha256_file(profile_file)!=rm["result_sha256"]:raise ForensicError(f"{symbol}: replay result SHA mismatch")
        replay_rows=[]
        for row in read_jsonl(profile_file):
            p=profile_from_row(row)
            replay_rows.append((str(row["as_of"])[:10],p))
        replay_rows.sort(key=lambda x:x[0])

        # Compute bearish streak using only replay history available up to each as_of.
        streak_by_date={}
        previous_direction=None
        streak=0
        for as_of,p in replay_rows:
            if p is None:
                streak_by_date[as_of]=(0,False,None)
                continue
            d=str(p.get("direction") or "").upper()
            transitioned=d in BEARISH_CLASSES and previous_direction not in BEARISH_CLASSES
            if d in BEARISH_CLASSES:streak=streak+1 if previous_direction in BEARISH_CLASSES else 1
            else:streak=0
            streak_by_date[as_of]=(streak,transitioned,previous_direction)
            previous_direction=d

        profile_map={d:p for d,p in replay_rows if p is not None}

        outcome_file=resolve(root,om["outcome_file"])
        if sha256_file(outcome_file)!=om["outcome_sha256"]:raise ForensicError(f"{symbol}: outcome SHA mismatch")
        for row in read_jsonl(outcome_file):
            native=str(row.get("native_direction") or row.get("direction") or "").upper()
            if native not in BEARISH_CLASSES:continue
            as_of=str(row["as_of"])[:10];profile=profile_map.get(as_of)
            if profile is None:raise ForensicError(f"{symbol} {as_of}: bearish profile missing")
            streak,transitioned,previous=streak_by_date[as_of]
            life=lifecycle_label(streak)
            d0=dt.date.fromisoformat(as_of)
            p5=prior_return(dates,closes,d0,5);p10=prior_return(dates,closes,d0,10);p20=prior_return(dates,closes,d0,20)
            dd63=drawdown_from_prior_high(dates,closes,d0,63)
            flags=overlay_flags(profile,p10,p20,dd63)
            transition_counts[(life,"transitioned" if transitioned else "persistent")]+=1

            for h in FIXED_HORIZONS:
                o=row["outcomes"][str(h)]
                if o.get("status")!="MATURED":continue
                dret=-float(o["forward_return"])
                grouped[life][h].append(dret)
                grouped[f"CLASS::{native}::{life}"][h].append(dret)
                grouped["ALL_BEARISH"][h].append(dret)
                for name,active in flags.items():
                    if active:
                        overlay_grouped[f"{life}::{name}"][h].append(dret)
                        overlay_grouped[f"ALL::{name}"][h].append(dret)
                rows_out.append({
                    "symbol":symbol,"as_of":as_of,"horizon_sessions":h,
                    "native_direction":native,"lifecycle_state":life,
                    "bearish_streak_observations":streak,"transitioned_into_bearish":transitioned,
                    "previous_direction":previous,
                    "prior_5_session_return":p5,"prior_10_session_return":p10,
                    "prior_20_session_return":p20,"drawdown_from_prior_63_session_high":dd63,
                    "breakout_state":str(get_path(profile,"breakout.state") or ""),
                    "participation_state":str(get_path(profile,"participation.state") or ""),
                    "strong_bearish_timeframe_count":strong_bearish_tf_count(profile),
                    **{f"overlay_{k}":v for k,v in flags.items()},
                    "realized_bearish_directional_return":dret,
                })

    summaries={}
    for key,hmap in sorted(grouped.items()):
        summaries[key]={str(h):stats(hmap.get(h,[])) for h in FIXED_HORIZONS}
    overlay_summaries={}
    for key,hmap in sorted(overlay_grouped.items()):
        overlay_summaries[key]={str(h):stats(hmap.get(h,[])) for h in FIXED_HORIZONS}

    # Primary monotonicity diagnostic: does future bearish edge degrade with maturity?
    maturity_order=("EARLY_TRANSITION","ESTABLISHED","PERSISTENT_LATE")
    maturity_diag={}
    for h in FIXED_HORIZONS:
        means=[summaries[s][str(h)]["mean"] for s in maturity_order]
        accs=[summaries[s][str(h)]["accuracy"] for s in maturity_order]
        maturity_diag[str(h)]={
            "mean_directional_returns":dict(zip(maturity_order,means)),
            "accuracies":dict(zip(maturity_order,accs)),
            "mean_degrades_with_maturity":all(means[i+1] <= means[i] for i in range(len(means)-1)),
            "accuracy_degrades_with_maturity":all(accs[i+1] <= accs[i] for i in range(len(accs)-1)),
        }

    report={
        "version":VERSION,"status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "robust_authority_sha256":sha256_file(bp),
        "successful_symbol_count":EXPECTED_SYMBOLS,
        "fixed_horizons_sessions":list(FIXED_HORIZONS),
        "lifecycle_definition":{
            "EARLY_TRANSITION":f"bearish streak 1-{EARLY_MAX_STREAK} WEEKLY observations",
            "ESTABLISHED":f"bearish streak {EARLY_MAX_STREAK+1}-{ESTABLISHED_MAX_STREAK} WEEKLY observations",
            "PERSISTENT_LATE":f"bearish streak >= {PERSISTENT_LATE_MIN_STREAK} WEEKLY observations",
        },
        "fixed_exhaustion_overlays":{
            "prior_20_decline_threshold":PRIOR_20_DECLINE_THRESHOLD,
            "prior_10_decline_threshold":PRIOR_10_DECLINE_THRESHOLD,
            "drawdown_63_threshold":DRAWDOWN_63_THRESHOLD,
            "strong_bearish_timeframe_count_min":STRONG_ALIGNMENT_MIN_COUNT,
            "breakdown_confirmed_state":"BREAKDOWN_CONFIRMED",
            "capitulation_state":"CAPITULATION",
        },
        "lifecycle_summaries":summaries,
        "overlay_summaries":overlay_summaries,
        "maturity_diagnostics":maturity_diag,
        "transition_counts":{f"{k[0]}::{k[1]}":v for k,v in transition_counts.items()},
        "governance":{
            "point_in_time_features_only":True,
            "future_bars_used_for_lifecycle_feature_construction":False,
            "future_bars_used_for_realized_outcome_labels_only":True,
            "polygon_api_queried":False,"database_access":"NONE","price_history_table_used":False,
            "frozen_polygon_materialization_used":True,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,"classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_authority_effect":False,"production_model_change_authorized":False,
        },
        "decision_gate":{
            "bearish_lifecycle_causal_forensics_complete":True,
            "bearish_semantic_change_authorized":False,
            "next_step":"REVIEW_M77_19_7_4_6_LIFECYCLE_EVIDENCE_BEFORE_ANY_CAUSAL_SEMANTIC_INTERVENTION",
        },
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows_out[0].keys()) if rows_out else []
    with outc.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows_out)

    print("=== M77.19.7.4.6 BEARISH LIFECYCLE / EXHAUSTION VS CONTINUATION CAUSAL FORENSICS ===")
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOLS}")
    for h in FIXED_HORIZONS:
        print(f"horizon_{h}_maturity: {maturity_diag[str(h)]}")
        for life in maturity_order:
            s=summaries[life][str(h)]
            print(f"horizon_{h}_{life}: count={s['count']} accuracy={s['accuracy']} mean={s['mean']} median={s['median']}")
        for overlay in ("BREAKDOWN_CONFIRMED","CAPITULATION","PRIOR_20_DECLINE_GE_10PCT","DRAWDOWN_63_GE_15PCT","STRONG_BEARISH_ALIGNMENT_2PLUS"):
            for life in maturity_order:
                s=overlay_summaries.get(f"{life}::{overlay}",{}).get(str(h))
                if s and s["count"]:
                    print(f"horizon_{h}_{life}_{overlay}: count={s['count']} accuracy={s['accuracy']} mean={s['mean']} median={s['median']}")
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_6_LIFECYCLE_EVIDENCE_BEFORE_ANY_CAUSAL_SEMANTIC_INTERVENTION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
