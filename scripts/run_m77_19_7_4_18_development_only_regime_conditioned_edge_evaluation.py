#!/usr/bin/env python3
"""
M77.19.7.4.18 — Development-Only Regime-Conditioned Edge Evaluation

Scores ONLY DEVELOPMENT observations (<= 2017-12-31) for the frozen candidate
definitions and frozen RC1-RC5 regime combinations preregistered by 7.4.17.

Validation and Final Holdout are not scored or used for advancement here.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.18-DEVELOPMENT-ONLY-REGIME-CONDITIONED-EDGE-EVALUATION-1.0"
EXPECTED_REGIME_VERSION="M77.19.7.4.17-REGIME-THRESHOLD-COMBINATION-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_CONTEXT_VERSION="M77.19.7.4.16-PIT-REGIME-CONTEXT-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
DEV_END="2017-12-31"
MIN_DEV_CELL_COUNT=500
HORIZONS=(5,10,20)

CANDIDATES={
    "H2_BREAKDOWN_INITIATION":(5,10),
    "H4_ROOM_PCT_GE_10PCT":(5,10,20),
    "H4_ROOM_PCT_5_10PCT":(5,10,20),
}
REGIME_IDS=(
    "RC1_DOWNTREND_HIGH_VOL",
    "RC2_BEAR_MARKET_WEAK_BREADTH",
    "RC3_DOWN_DRIFT_HIGH_VOL",
    "RC4_DOWNTREND_WEAK_BREADTH",
    "RC5_CORRECTION_OR_BEAR_HIGH_VOL",
)

class EvalError(RuntimeError): pass

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

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise EvalError(f"{path}:{i}: invalid JSONL") from exc

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
    }

def h2_match(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and str(row.get("breakout_state","")).upper()=="BREAKDOWN_SETUP"
        and int(float(row.get("bearish_streak_observations") or 0))<=2
    )

def classify_regimes(ctx:Mapping[str,Any], thresholds:Mapping[str,Any])->dict[str,bool]:
    def f(k):
        v=ctx.get(k)
        return None if v in (None,"") else float(v)
    vol=f("spy_realized_vol_26w_annualized")
    r13=f("spy_return_13w")
    r26=f("spy_return_26w")
    dd=f("spy_drawdown_from_52w_peak")
    bear_breadth=f("breadth_bearish_fraction")
    bull_breadth=f("breadth_bullish_fraction")
    spy_dir=str(ctx.get("spy_direction") or "").upper()

    vol_t=thresholds["VOLATILITY"]
    high_vol=(vol is not None and vol>=float(vol_t["normal_to_high"]))

    drift_t=thresholds["MARKET_DRIFT"]
    down_drift=(r26 is not None and r26<float(drift_t["down_to_neutral"]))

    bm_t=thresholds["BEAR_MARKET_CONTEXT"]
    correction_or_bear=(dd is not None and dd<=float(bm_t["normal_to_correction"]))
    bear_market=(dd is not None and dd<=float(bm_t["correction_to_bear"]))

    br_t=thresholds["BREADTH_REGIME"]
    weak_breadth=(
        bear_breadth is not None and bull_breadth is not None
        and bear_breadth>=float(br_t["bearish_high_threshold"])
        and bull_breadth<float(br_t["bullish_high_threshold"])
    )

    downtrend=(
        r13 is not None and r26 is not None
        and r13<0 and r26<0
        and spy_dir in ("BEARISH","STRONG_BEARISH")
    )

    return {
        "RC1_DOWNTREND_HIGH_VOL":downtrend and high_vol,
        "RC2_BEAR_MARKET_WEAK_BREADTH":bear_market and weak_breadth,
        "RC3_DOWN_DRIFT_HIGH_VOL":down_drift and high_vol,
        "RC4_DOWNTREND_WEAK_BREADTH":downtrend and weak_breadth,
        "RC5_CORRECTION_OR_BEAR_HIGH_VOL":correction_or_bear and high_vol,
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
    ap.add_argument("--regime-authority-json",default="reports/m77_19_7_4_17_regime_threshold_and_combination_preregistration_authority.json")
    ap.add_argument("--context-authority-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--lifecycle-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_18_development_only_regime_conditioned_edge_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_18_development_regime_candidate_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.regime_authority_json)
    cp=resolve(root,args.context_authority_json)
    cc=resolve(root,args.context_csv)
    lc=resolve(root,args.lifecycle_csv)
    hp=resolve(root,args.h4_authority_json)
    op=resolve(root,args.outcome_authority_json)

    reg=load_json(rp); ctxauth=load_json(cp); h4=load_json(hp); outcome=load_json(op)
    if reg.get("version")!=EXPECTED_REGIME_VERSION or reg.get("status")!="READY":
        raise EvalError("7.4.17 authority invalid")
    if ctxauth.get("version")!=EXPECTED_CONTEXT_VERSION or ctxauth.get("status")!="READY":
        raise EvalError("7.4.16 authority invalid")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise EvalError("outcome SHA mismatch")

    thresholds=reg.get("thresholds") or {}
    combos=[x["id"] for x in reg.get("predeclared_regime_combinations") or []]
    if tuple(combos)!=REGIME_IDS:raise EvalError("regime combination set differs from preregistration")
    if reg.get("preregistration_contract",{}).get("minimum_development_cell_count_for_future_scoring")!=MIN_DEV_CELL_COUNT:
        raise EvalError("Development minimum cell count mismatch")

    # Development context only.
    context={}
    with cc.open("r",encoding="utf-8",newline="") as fh:
        for row in csv.DictReader(fh):
            if row["partition"]!="DEVELOPMENT":continue
            if row["as_of"]>DEV_END:continue
            context[row["as_of"]]=classify_regimes(row,thresholds)

    if len(context)!=ctxauth.get("development_context_row_count"):
        raise EvalError("Development context row count mismatch")

    buckets=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    candidate_baseline=defaultdict(lambda:defaultdict(list))

    # H2 source: lifecycle evidence, Development only.
    with lc.open("r",encoding="utf-8",newline="") as fh:
        for row in csv.DictReader(fh):
            as_of=row["as_of"][:10]
            if as_of>DEV_END:continue
            if as_of not in context:continue
            h=int(row["horizon_sessions"])
            if h not in CANDIDATES["H2_BREAKDOWN_INITIATION"]:continue
            if not h2_match(row):continue
            y=float(row["realized_bearish_directional_return"])
            candidate_baseline["H2_BREAKDOWN_INITIATION"][h].append(y)
            for rc,active in context[as_of].items():
                if active:buckets["H2_BREAKDOWN_INITIATION"][rc][h].append(y)

    # H4 geometry index, Development only.
    geom={}
    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["materialization_file"])
        if sha256_file(f)!=sm["materialization_sha256"]:
            raise EvalError(f"{symbol}: H4 materialization SHA mismatch")
        for row in iter_jsonl(f):
            if row.get("partition")!="DEVELOPMENT":continue
            as_of=str(row["as_of"])[:10]
            if as_of>DEV_END:continue
            b=row.get("nearest_structural_room_pct_bin")
            if b in ("GE_10PCT","5_10PCT"):
                geom[(symbol,as_of)] = b

    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    for symbol,sm in oms.items():
        of=resolve(root,sm["outcome_file"])
        if sha256_file(of)!=sm["outcome_sha256"]:
            raise EvalError(f"{symbol}: outcome SHA mismatch")
        for row in iter_jsonl(of):
            as_of=str(row["as_of"])[:10]
            if as_of>DEV_END or as_of not in context:continue
            b=geom.get((symbol,as_of))
            if b is None:continue
            cid="H4_ROOM_PCT_GE_10PCT" if b=="GE_10PCT" else "H4_ROOM_PCT_5_10PCT"
            for h in CANDIDATES[cid]:
                o=(row.get("outcomes") or {}).get(str(h)) or {}
                if o.get("status")!="MATURED":continue
                y=-float(o["forward_return"])
                candidate_baseline[cid][h].append(y)
                for rc,active in context[as_of].items():
                    if active:buckets[cid][rc][h].append(y)

    evidence=[]
    for cid,horizons in CANDIDATES.items():
        for rc in REGIME_IDS:
            for h in horizons:
                s=stats(buckets[cid][rc][h]); b=stats(candidate_baseline[cid][h])
                evidence.append({
                    "candidate_id":cid,
                    "regime_id":rc,
                    "horizon_sessions":h,
                    **s,
                    "candidate_unconditioned_count":b["count"],
                    "candidate_unconditioned_accuracy":b["accuracy"],
                    "candidate_unconditioned_median":b["median"],
                    "accuracy_delta_vs_unconditioned_candidate":None if s["accuracy"] is None else s["accuracy"]-b["accuracy"],
                    "median_delta_vs_unconditioned_candidate":None if s["median"] is None else s["median"]-b["median"],
                    "eligible_for_interpretation":s["count"]>=MIN_DEV_CELL_COUNT,
                    "positive_edge_cell":(
                        s["count"]>=MIN_DEV_CELL_COUNT
                        and s["accuracy"] is not None and s["accuracy"]>0.5
                        and s["median"] is not None and s["median"]>0
                    ),
                })

    positive=[x for x in evidence if x["positive_edge_cell"]]
    report={
        "version":VERSION,
        "status":"READY",
        "regime_authority_sha256":sha256_file(rp),
        "context_authority_sha256":sha256_file(cp),
        "context_csv_sha256":sha256_file(cc),
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "development_end":DEV_END,
        "minimum_development_cell_count":MIN_DEV_CELL_COUNT,
        "candidate_scope":{k:list(v) for k,v in CANDIDATES.items()},
        "regime_scope":list(REGIME_IDS),
        "evidence":evidence,
        "development_positive_edge_cells":[
            {
                "candidate_id":x["candidate_id"],
                "regime_id":x["regime_id"],
                "horizon_sessions":x["horizon_sessions"],
                "count":x["count"],
                "accuracy":x["accuracy"],
                "median":x["median"],
                "accuracy_delta_vs_unconditioned_candidate":x["accuracy_delta_vs_unconditioned_candidate"],
                "median_delta_vs_unconditioned_candidate":x["median_delta_vs_unconditioned_candidate"],
            }
            for x in positive
        ],
        "evaluation_scope":{
            "development_only":True,
            "validation_context_used_for_scoring":False,
            "validation_candidate_outcomes_used":False,
            "final_holdout_context_used":False,
            "final_holdout_candidate_outcomes_used":False,
            "candidate_definitions_changed":False,
            "regime_thresholds_changed":False,
            "regime_combinations_changed":False,
            "validation_advancement_selected":False,
        },
        "governance":{
            "threshold_search_or_optimization":False,
            "regime_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_18_DEVELOPMENT_REGIME_CONDITIONED_EVIDENCE_BEFORE_ANY_VALIDATION_ADVANCEMENT",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(evidence[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(evidence)

    print("=== M77.19.7.4.18 DEVELOPMENT-ONLY REGIME-CONDITIONED EDGE EVALUATION ===")
    print("status: READY")
    print(f"development_context_row_count: {len(context)}")
    print(f"minimum_development_cell_count: {MIN_DEV_CELL_COUNT}")
    for e in evidence:
        print(f"{e['candidate_id']}__{e['regime_id']}__h{e['horizon_sessions']}: "
              f"count={e['count']} accuracy={e['accuracy']} median={e['median']} "
              f"accuracy_delta={e['accuracy_delta_vs_unconditioned_candidate']} "
              f"median_delta={e['median_delta_vs_unconditioned_candidate']} "
              f"eligible={e['eligible_for_interpretation']} positive_edge={e['positive_edge_cell']}")
    print("development_positive_edge_cell_count:", len(positive))
    print("development_positive_edge_cells:",
          [(x["candidate_id"],x["regime_id"],x["horizon_sessions"]) for x in positive])
    print("validation_context_used_for_scoring: False")
    print("validation_candidate_outcomes_used: False")
    print("final_holdout_context_used: False")
    print("final_holdout_candidate_outcomes_used: False")
    print("validation_advancement_selected: False")
    print("threshold_search_or_optimization: False")
    print("regime_search_or_optimization: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_18_DEVELOPMENT_REGIME_CONDITIONED_EVIDENCE_BEFORE_ANY_VALIDATION_ADVANCEMENT")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
