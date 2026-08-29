#!/usr/bin/env python3
"""
M77.19.7.4.17 — Regime Threshold & Combination Preregistration Authority

Freezes regime thresholds using only point-in-time regime-context observables
from M77.19.7.4.16. No candidate outcome is read or scored.

Thresholds are rule-based / distributional on DEVELOPMENT context only and are
frozen before any regime-conditioned candidate evaluation.

Validation context may be present in the source file but is not used to choose
thresholds. Final Holdout remains absent and sealed.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, os, statistics, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.7.4.17-REGIME-THRESHOLD-COMBINATION-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_CONTEXT_VERSION="M77.19.7.4.16-PIT-REGIME-CONTEXT-MATERIALIZATION-AUTHORITY-1.0"
DEV_END="2017-12-31"
FINAL_HOLDOUT_START="2023-01-01"

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
    if p.exists(): return p
    q=root/p
    return q if q.exists() else p

def quantile(xs:list[float], q:float)->float:
    if not xs: raise AuthorityError("empty quantile input")
    ys=sorted(xs)
    if len(ys)==1:return ys[0]
    pos=(len(ys)-1)*q
    lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi:return ys[lo]
    w=pos-lo
    return ys[lo]*(1-w)+ys[hi]*w

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent); os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--context-authority-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_17_regime_threshold_and_combination_preregistration_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_17_regime_threshold_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    apath=resolve(root,args.context_authority_json)
    cpath=resolve(root,args.context_csv)

    auth=load_json(apath)
    if auth.get("version")!=EXPECTED_CONTEXT_VERSION or auth.get("status")!="READY":
        raise AuthorityError("M77.19.7.4.16 context authority invalid")
    if auth.get("final_holdout_protection",{}).get("context_rows_materialized")!=0:
        raise AuthorityError("Final Holdout context must remain absent")

    with cpath.open("r",encoding="utf-8",newline="") as fh:
        rows=list(csv.DictReader(fh))
    if not rows: raise AuthorityError("empty context CSV")

    dev=[r for r in rows if r["partition"]=="DEVELOPMENT" and r["as_of"]<=DEV_END]
    val=[r for r in rows if r["partition"]=="VALIDATION"]
    if len(dev)!=auth.get("development_context_row_count"):
        raise AuthorityError("Development context count mismatch")
    if len(val)!=auth.get("validation_context_row_count"):
        raise AuthorityError("Validation context count mismatch")
    if any(r["as_of"]>=FINAL_HOLDOUT_START for r in rows):
        raise AuthorityError("Final Holdout row present in context CSV")

    def vals(field):
        out=[]
        for r in dev:
            raw=r.get(field)
            if raw in ("",None):continue
            try:v=float(raw)
            except Exception:continue
            if math.isfinite(v):out.append(v)
        if not out: raise AuthorityError(f"no Development values for {field}")
        return out

    # Distributional thresholds are computed ONLY from Development PIT context.
    vol26=vals("spy_realized_vol_26w_annualized")
    breadth_bear=vals("breadth_bearish_fraction")
    breadth_bull=vals("breadth_bullish_fraction")
    ret26=vals("spy_return_26w")
    dd52=vals("spy_drawdown_from_52w_peak")

    thresholds={
        "VOLATILITY":{
            "source_field":"spy_realized_vol_26w_annualized",
            "method":"DEVELOPMENT_TERCILES",
            "low_to_normal":quantile(vol26,1/3),
            "normal_to_high":quantile(vol26,2/3),
            "categories":["LOW_VOL","NORMAL_VOL","HIGH_VOL"],
        },
        "MARKET_DRIFT":{
            "source_field":"spy_return_26w",
            "method":"FIXED_ZERO_AND_10PCT_BANDS",
            "down_to_neutral":-0.10,
            "neutral_to_up":0.10,
            "categories":["DOWN_DRIFT","NEUTRAL_DRIFT","UP_DRIFT"],
        },
        "BREADTH_REGIME":{
            "source_fields":["breadth_bearish_fraction","breadth_bullish_fraction"],
            "method":"DEVELOPMENT_TERCILES_SIDE_SPECIFIC",
            "bearish_high_threshold":quantile(breadth_bear,2/3),
            "bullish_high_threshold":quantile(breadth_bull,2/3),
            "categories":["WEAK","MIXED","BROAD"],
        },
        "BEAR_MARKET_CONTEXT":{
            "source_field":"spy_drawdown_from_52w_peak",
            "method":"FIXED_DRAWDOWN_BANDS",
            "normal_to_correction":-0.10,
            "correction_to_bear":-0.20,
            "categories":["NORMAL","CORRECTION","BEAR_MARKET"],
        },
        "TREND_REGIME":{
            "source_fields":["spy_return_13w","spy_return_26w","spy_direction"],
            "method":"FIXED_DIRECTION_CONCORDANCE",
            "uptrend_rule":"spy_return_13w > 0 AND spy_return_26w > 0 AND spy_direction in {BULLISH,STRONG_BULLISH}",
            "downtrend_rule":"spy_return_13w < 0 AND spy_return_26w < 0 AND spy_direction in {BEARISH,STRONG_BEARISH}",
            "else_rule":"SIDEWAYS",
            "categories":["UPTREND","SIDEWAYS","DOWNTREND"],
        },
    }

    combinations=[
        {
            "id":"RC1_DOWNTREND_HIGH_VOL",
            "conditions":["TREND_REGIME=DOWNTREND","VOLATILITY=HIGH_VOL"],
            "rationale":"Separate stressed persistent downside from ordinary bearish state.",
        },
        {
            "id":"RC2_BEAR_MARKET_WEAK_BREADTH",
            "conditions":["BEAR_MARKET_CONTEXT=BEAR_MARKET","BREADTH_REGIME=WEAK"],
            "rationale":"Separate broad market stress with weak cross-sectional participation.",
        },
        {
            "id":"RC3_DOWN_DRIFT_HIGH_VOL",
            "conditions":["MARKET_DRIFT=DOWN_DRIFT","VOLATILITY=HIGH_VOL"],
            "rationale":"Separate negative medium-term drift with elevated volatility.",
        },
        {
            "id":"RC4_DOWNTREND_WEAK_BREADTH",
            "conditions":["TREND_REGIME=DOWNTREND","BREADTH_REGIME=WEAK"],
            "rationale":"Separate aligned market trend and breadth deterioration.",
        },
        {
            "id":"RC5_CORRECTION_OR_BEAR_HIGH_VOL",
            "conditions":["BEAR_MARKET_CONTEXT in {CORRECTION,BEAR_MARKET}","VOLATILITY=HIGH_VOL"],
            "rationale":"Separate material drawdown context with elevated realized volatility.",
        },
    ]

    report={
        "version":VERSION,
        "status":"READY",
        "context_authority_sha256":sha256_file(apath),
        "context_csv_sha256":sha256_file(cpath),
        "development_context_row_count":len(dev),
        "validation_context_row_count_present_but_unused_for_threshold_selection":len(val),
        "thresholds":thresholds,
        "predeclared_regime_combinations":combinations,
        "preregistration_contract":{
            "candidate_outcomes_read":False,
            "candidate_performance_scored":False,
            "validation_context_used_to_choose_thresholds":False,
            "validation_context_used_to_choose_combinations":False,
            "final_holdout_context_available":False,
            "thresholds_frozen_after_this_authority":True,
            "combinations_frozen_after_this_authority":True,
            "minimum_development_cell_count_for_future_scoring":500,
            "minimum_validation_cell_count_for_future_scoring":300,
        },
        "governance":{
            "threshold_search_against_outcomes":False,
            "combination_search_against_outcomes":False,
            "parameter_fitting_against_candidate_returns":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_18_DEVELOPMENT_ONLY_REGIME_CONDITIONED_EDGE_EVALUATION",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)

    rows_out=[]
    for k,v in thresholds.items():
        rows_out.append({
            "regime_dimension":k,
            "method":v["method"],
            "source_fields":"|".join(v.get("source_fields") or [v.get("source_field")]),
            "categories":"|".join(v["categories"]),
            "definition_json":json.dumps(v,sort_keys=True),
        })
    outc.parent.mkdir(parents=True,exist_ok=True)
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows_out[0].keys()))
        w.writeheader();w.writerows(rows_out)

    print("=== M77.19.7.4.17 REGIME THRESHOLD & COMBINATION PREREGISTRATION AUTHORITY ===")
    print("status: READY")
    print(f"development_context_row_count: {len(dev)}")
    print(f"validation_context_row_count_present_but_unused_for_threshold_selection: {len(val)}")
    print("volatility_thresholds:", thresholds["VOLATILITY"])
    print("market_drift_thresholds:", thresholds["MARKET_DRIFT"])
    print("breadth_thresholds:", thresholds["BREADTH_REGIME"])
    print("bear_market_thresholds:", thresholds["BEAR_MARKET_CONTEXT"])
    print("trend_regime_method:", thresholds["TREND_REGIME"]["method"])
    print("predeclared_regime_combinations:", [x["id"] for x in combinations])
    print("candidate_outcomes_read: False")
    print("candidate_performance_scored: False")
    print("validation_context_used_to_choose_thresholds: False")
    print("validation_context_used_to_choose_combinations: False")
    print("final_holdout_context_available: False")
    print("thresholds_frozen_after_this_authority: True")
    print("combinations_frozen_after_this_authority: True")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_18_DEVELOPMENT_ONLY_REGIME_CONDITIONED_EDGE_EVALUATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
