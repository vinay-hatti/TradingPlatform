#!/usr/bin/env python3
"""
M77.19.7.4.16 — Point-in-Time Regime Context Materialization Authority

Materializes continuous, point-in-time market-regime observables for
DEVELOPMENT + VALIDATION only. No candidate outcomes are used to define regimes.
No regime categories or thresholds are fitted in this milestone.

Final Holdout >= 2023-01-01 is not read or materialized.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.7.4.16-PIT-REGIME-CONTEXT-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_RESEARCH_VERSION="M77.19.7.4.15-REGIME-CONDITIONED-PROSPECTIVE-EDGE-RESEARCH-AUTHORITY-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
END_DATE="2022-12-31"
FINAL_HOLDOUT_START="2023-01-01"
EXPECTED_SYMBOLS=602

class AuthorityError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():return p
    if not p.is_absolute():
        q=root/p
        if q.exists():return q
    for anchor in ("reports","research_data","data"):
        if anchor in p.parts:
            q=root.joinpath(*p.parts[p.parts.index(anchor):])
            if q.exists():return q
    return p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise AuthorityError(f"{path}:{i}: invalid JSONL") from exc

def num(v:Any)->float|None:
    if v is None:return None
    try:x=float(v)
    except Exception:return None
    return x if math.isfinite(x) else None

def get_path(obj:Any,path:str)->Any:
    cur=obj
    for p in path.split("."):
        if not isinstance(cur,dict) or p not in cur:return None
        cur=cur[p]
    return cur

def classify_direction(v:Any)->str:
    s=str(v or "").upper()
    if s in ("BULLISH","STRONG_BULLISH"):return "BULLISH"
    if s in ("BEARISH","STRONG_BEARISH"):return "BEARISH"
    return "NEUTRAL"

def rolling_return(closes:list[float], periods:int)->float|None:
    if len(closes)<=periods:return None
    base=closes[-1-periods]
    return None if base<=0 else closes[-1]/base-1.0

def rolling_vol(closes:list[float], periods:int)->float|None:
    if len(closes)<=periods:return None
    xs=closes[-(periods+1):]
    rets=[xs[i]/xs[i-1]-1.0 for i in range(1,len(xs)) if xs[i-1]>0]
    if len(rets)<2:return None
    return statistics.stdev(rets)*math.sqrt(52.0)

def drawdown_from_peak(closes:list[float], periods:int)->float|None:
    if not closes:return None
    xs=closes[-min(periods,len(closes)):]
    peak=max(xs)
    return None if peak<=0 else closes[-1]/peak-1.0

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
    ap.add_argument("--research-authority-json",default="reports/m77_19_7_4_15_regime_conditioned_prospective_edge_research_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    apath=resolve(root,args.research_authority_json)
    rpath=resolve(root,args.replay_authority_json)
    opath=resolve(root,args.outcome_authority_json)

    auth=load_json(apath); replay=load_json(rpath); outcome=load_json(opath)
    if auth.get("version")!=EXPECTED_RESEARCH_VERSION or auth.get("status")!="READY":
        raise AuthorityError("M77.19.7.4.15 authority invalid")
    if sha256_file(rpath)!=EXPECTED_REPLAY_SHA:raise AuthorityError("replay SHA mismatch")
    if sha256_file(opath)!=EXPECTED_OUTCOME_SHA:raise AuthorityError("outcome SHA mismatch")
    if replay.get("successful_symbol_cadence_replay_count")!=EXPECTED_SYMBOLS:
        raise AuthorityError("replay symbol count mismatch")

    # Aggregate cross-sectional state by as_of using only PIT replay profiles <= 2022-12-31.
    cross=defaultdict(Counter)
    spy_profile={}
    skipped_final_profile_rows=0
    weekly=[x for x in replay.get("symbols") or [] if x.get("cadence")=="WEEKLY"]
    if len(weekly)!=EXPECTED_SYMBOLS:raise AuthorityError("weekly replay symbol count mismatch")
    for sm in weekly:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["result_file"])
        if sha256_file(f)!=sm["result_sha256"]:raise AuthorityError(f"{symbol}: replay SHA mismatch")
        for row in iter_jsonl(f):
            if row.get("status")!="REPLAYED":continue
            as_of=str(row["as_of"])[:10]
            if as_of>=FINAL_HOLDOUT_START:
                skipped_final_profile_rows+=1
                continue
            if as_of>END_DATE:continue
            p=row.get("profile")
            if not isinstance(p,dict):raise AuthorityError(f"{symbol}: missing full profile")
            d=classify_direction(p.get("direction"))
            c=cross[as_of]
            c["eligible"]+=1
            c[f"direction_{d}"]+=1
            bo=str(get_path(p,"breakout.state") or "").upper()
            if bo:c[f"breakout_{bo}"]+=1
            part=str(get_path(p,"participation.state") or "").upper()
            if part:c[f"participation_{part}"]+=1
            if symbol=="SPY":
                spy_profile[as_of]={
                    "spy_direction":str(p.get("direction") or ""),
                    "spy_confidence":num(p.get("confidence")),
                    "spy_overall_score":num(row.get("overall_score")),
                    "spy_breakout_state":bo or None,
                    "spy_participation_state":part or None,
                }

    # Resolve same-as-of SPY base close from outcome authority. This is a contemporaneous
    # price field only; no forward return, maturity result, or outcome label is consumed.
    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    if "SPY" not in oms:raise AuthorityError("SPY missing from outcome authority")
    spyom=oms["SPY"]
    spyfile=resolve(root,spyom["outcome_file"])
    if sha256_file(spyfile)!=spyom["outcome_sha256"]:raise AuthorityError("SPY outcome SHA mismatch")

    spy_close={}
    skipped_final_outcome_rows=0
    for row in iter_jsonl(spyfile):
        as_of=str(row["as_of"])[:10]
        if as_of>=FINAL_HOLDOUT_START:
            skipped_final_outcome_rows+=1
            continue
        if as_of>END_DATE:continue
        base=None
        for h in ("5","10","20"):
            o=(row.get("outcomes") or {}).get(h) or {}
            v=num(o.get("base_close"))
            if v is not None and v>0:
                base=v;break
        if base is not None:spy_close[as_of]=base

    dates=sorted(set(cross) & set(spy_close))
    rows=[]
    closes=[]
    for as_of in dates:
        closes.append(spy_close[as_of])
        c=cross[as_of]
        n=c["eligible"]
        if n<=0:continue
        rec={
            "as_of":as_of,
            "partition":"DEVELOPMENT" if as_of<="2017-12-31" else "VALIDATION",
            "cross_section_eligible_count":n,
            "breadth_bullish_fraction":c["direction_BULLISH"]/n,
            "breadth_bearish_fraction":c["direction_BEARISH"]/n,
            "breadth_neutral_fraction":c["direction_NEUTRAL"]/n,
            "breakdown_setup_fraction":c["breakout_BREAKDOWN_SETUP"]/n,
            "breakdown_confirmed_fraction":c["breakout_BREAKDOWN_CONFIRMED"]/n,
            "capitulation_fraction":c["participation_CAPITULATION"]/n,
            "spy_close":spy_close[as_of],
            "spy_return_4w":rolling_return(closes,4),
            "spy_return_13w":rolling_return(closes,13),
            "spy_return_26w":rolling_return(closes,26),
            "spy_realized_vol_13w_annualized":rolling_vol(closes,13),
            "spy_realized_vol_26w_annualized":rolling_vol(closes,26),
            "spy_drawdown_from_52w_peak":drawdown_from_peak(closes,52),
            **(spy_profile.get(as_of) or {
                "spy_direction":None,"spy_confidence":None,"spy_overall_score":None,
                "spy_breakout_state":None,"spy_participation_state":None
            }),
        }
        rows.append(rec)

    if not rows:raise AuthorityError("no PIT regime rows materialized")

    summary={
        "version":VERSION,
        "status":"READY",
        "research_authority_sha256":sha256_file(apath),
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "materialized_context_row_count":len(rows),
        "development_context_row_count":sum(r["partition"]=="DEVELOPMENT" for r in rows),
        "validation_context_row_count":sum(r["partition"]=="VALIDATION" for r in rows),
        "first_context_as_of":rows[0]["as_of"],
        "last_context_as_of":rows[-1]["as_of"],
        "continuous_observables":[
            "breadth_bullish_fraction","breadth_bearish_fraction","breadth_neutral_fraction",
            "breakdown_setup_fraction","breakdown_confirmed_fraction","capitulation_fraction",
            "spy_return_4w","spy_return_13w","spy_return_26w",
            "spy_realized_vol_13w_annualized","spy_realized_vol_26w_annualized",
            "spy_drawdown_from_52w_peak","spy_direction","spy_confidence","spy_overall_score",
            "spy_breakout_state","spy_participation_state",
        ],
        "materialization_contract":{
            "candidate_outcomes_used_to_define_regime":False,
            "future_returns_used_to_define_regime":False,
            "same_as_of_spy_base_close_used":True,
            "cross_section_from_same_as_of_native_profiles_only":True,
            "regime_categories_materialized":False,
            "regime_thresholds_fitted":False,
            "regime_combinations_searched":False,
        },
        "final_holdout_protection":{
            "start":FINAL_HOLDOUT_START,
            "profile_rows_seen_and_skipped":skipped_final_profile_rows,
            "spy_outcome_rows_seen_and_skipped":skipped_final_outcome_rows,
            "context_rows_materialized":0,
            "candidate_scoring_performed":False,
            "diagnostic_regime_peeking_performed":False,
        },
        "governance":{
            "new_candidate_scored":False,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_17_REGIME_THRESHOLD_AND_COMBINATION_PREREGISTRATION_AUTHORITY",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,summary)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.7.4.16 POINT-IN-TIME REGIME CONTEXT MATERIALIZATION AUTHORITY ===")
    print("status: READY")
    print(f"materialized_context_row_count: {len(rows)}")
    print(f"development_context_row_count: {summary['development_context_row_count']}")
    print(f"validation_context_row_count: {summary['validation_context_row_count']}")
    print(f"first_context_as_of: {summary['first_context_as_of']}")
    print(f"last_context_as_of: {summary['last_context_as_of']}")
    print(f"final_holdout_profile_rows_seen_and_skipped: {skipped_final_profile_rows}")
    print(f"final_holdout_spy_outcome_rows_seen_and_skipped: {skipped_final_outcome_rows}")
    print("candidate_outcomes_used_to_define_regime: False")
    print("future_returns_used_to_define_regime: False")
    print("regime_categories_materialized: False")
    print("regime_thresholds_fitted: False")
    print("regime_combinations_searched: False")
    print("final_holdout_context_rows_materialized: 0")
    print("new_candidate_scored: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_17_REGIME_THRESHOLD_AND_COMBINATION_PREREGISTRATION_AUTHORITY")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
