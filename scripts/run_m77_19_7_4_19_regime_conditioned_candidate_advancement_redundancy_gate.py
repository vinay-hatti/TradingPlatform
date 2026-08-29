#!/usr/bin/env python3
"""
M77.19.7.4.19 — Regime-Conditioned Candidate Advancement & Redundancy Gate

Purpose:
- Freeze the small Development-selected regime-conditioned candidate family.
- Quantify Development-only membership overlap / redundancy.
- Collapse only near-duplicates using a preregistered Jaccard >= 0.90 rule.
- Finalize exact candidate/horizon scopes permitted to enter Validation.

Validation outcomes are not read.
Final Holdout is not read.
No production authority is changed.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.19-REGIME-CONDITIONED-CANDIDATE-ADVANCEMENT-REDUNDANCY-GATE-1.0"
EXPECTED_EVAL_VERSION="M77.19.7.4.18-DEVELOPMENT-ONLY-REGIME-CONDITIONED-EDGE-EVALUATION-1.0"
EXPECTED_REGIME_VERSION="M77.19.7.4.17-REGIME-THRESHOLD-COMBINATION-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_CONTEXT_VERSION="M77.19.7.4.16-PIT-REGIME-CONTEXT-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"

DEV_END="2017-12-31"
FINAL_HOLDOUT_START="2023-01-01"
NEAR_DUPLICATE_JACCARD=0.90
MIN_DEV_CELL_COUNT=500

# Deliberately frozen BEFORE Validation and BEFORE overlap is observed.
PRESELECTED={
    "RC_H4_GE10_DOWNTREND_HIGH_VOL":{
        "candidate_id":"H4_ROOM_PCT_GE_10PCT",
        "regime_id":"RC1_DOWNTREND_HIGH_VOL",
        "horizons":[5,10,20],
        "priority":1,
        "concept":"TREND_PLUS_VOLATILITY_STRESS",
    },
    "RC_H4_GE10_DOWNTREND_WEAK_BREADTH":{
        "candidate_id":"H4_ROOM_PCT_GE_10PCT",
        "regime_id":"RC4_DOWNTREND_WEAK_BREADTH",
        "horizons":[5,10,20],
        "priority":2,
        "concept":"TREND_PLUS_BREADTH_STRESS",
    },
    "RC_H4_5_10_BEAR_MARKET_WEAK_BREADTH":{
        "candidate_id":"H4_ROOM_PCT_5_10PCT",
        "regime_id":"RC2_BEAR_MARKET_WEAK_BREADTH",
        "horizons":[5,10,20],
        "priority":3,
        "concept":"BEAR_MARKET_PLUS_BREADTH_STRESS",
    },
}

class GateError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():return p
    if not p.is_absolute():
        q=root/p
        if q.exists():return q
    return p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise GateError(f"{path}:{i}: invalid JSONL") from exc

def h4_bin_for_candidate(candidate_id:str)->str:
    if candidate_id=="H4_ROOM_PCT_GE_10PCT":return "GE_10PCT"
    if candidate_id=="H4_ROOM_PCT_5_10PCT":return "5_10PCT"
    raise GateError(f"unsupported H4 candidate {candidate_id}")

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

    high_vol=vol is not None and vol>=float(thresholds["VOLATILITY"]["normal_to_high"])
    downtrend=(r13 is not None and r26 is not None and r13<0 and r26<0
               and spy_dir in ("BEARISH","STRONG_BEARISH"))
    bear_market=dd is not None and dd<=float(thresholds["BEAR_MARKET_CONTEXT"]["correction_to_bear"])
    weak_breadth=(bear_breadth is not None and bull_breadth is not None
                  and bear_breadth>=float(thresholds["BREADTH_REGIME"]["bearish_high_threshold"])
                  and bull_breadth<float(thresholds["BREADTH_REGIME"]["bullish_high_threshold"]))

    return {
        "RC1_DOWNTREND_HIGH_VOL":downtrend and high_vol,
        "RC2_BEAR_MARKET_WEAK_BREADTH":bear_market and weak_breadth,
        "RC4_DOWNTREND_WEAK_BREADTH":downtrend and weak_breadth,
    }

def jaccard(a:set[tuple[str,str]],b:set[tuple[str,str]])->float:
    u=a|b
    return 0.0 if not u else len(a&b)/len(u)

def containment(a:set[tuple[str,str]],b:set[tuple[str,str]])->tuple[float,float]:
    inter=len(a&b)
    return (
        0.0 if not a else inter/len(a),
        0.0 if not b else inter/len(b),
    )

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
    ap.add_argument("--development-eval-json",default="reports/m77_19_7_4_18_development_only_regime_conditioned_edge_evaluation.json")
    ap.add_argument("--regime-authority-json",default="reports/m77_19_7_4_17_regime_threshold_and_combination_preregistration_authority.json")
    ap.add_argument("--context-authority-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_19_regime_conditioned_candidate_advancement_redundancy_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_19_candidate_overlap_and_advancement.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    ep=resolve(root,args.development_eval_json)
    rp=resolve(root,args.regime_authority_json)
    cp=resolve(root,args.context_authority_json)
    cc=resolve(root,args.context_csv)
    hp=resolve(root,args.h4_authority_json)
    op=resolve(root,args.outcome_authority_json)

    ev=load_json(ep);reg=load_json(rp);ctxauth=load_json(cp);h4=load_json(hp);outcome=load_json(op)
    if ev.get("version")!=EXPECTED_EVAL_VERSION or ev.get("status")!="READY":
        raise GateError("7.4.18 authority invalid")
    if reg.get("version")!=EXPECTED_REGIME_VERSION or reg.get("status")!="READY":
        raise GateError("7.4.17 authority invalid")
    if ctxauth.get("version")!=EXPECTED_CONTEXT_VERSION or ctxauth.get("status")!="READY":
        raise GateError("7.4.16 authority invalid")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise GateError("outcome SHA mismatch")
    if ev.get("minimum_development_cell_count")!=MIN_DEV_CELL_COUNT:
        raise GateError("Development cell-count authority mismatch")

    # Require every preselected cell/horizon to have been Development positive in 7.4.18.
    eidx={(x["candidate_id"],x["regime_id"],int(x["horizon_sessions"])):x for x in ev.get("evidence") or []}
    for name,spec in PRESELECTED.items():
        for h in spec["horizons"]:
            x=eidx.get((spec["candidate_id"],spec["regime_id"],h))
            if not x:raise GateError(f"{name} h{h}: missing 7.4.18 evidence")
            if not x.get("eligible_for_interpretation") or not x.get("positive_edge_cell"):
                raise GateError(f"{name} h{h}: no longer satisfies frozen Development gate")

    thresholds=reg["thresholds"]

    # Development-only context membership by as_of.
    ctx={}
    with cc.open("r",encoding="utf-8",newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("partition")!="DEVELOPMENT":continue
            as_of=row["as_of"][:10]
            if as_of>DEV_END:continue
            ctx[as_of]=classify_regimes(row,thresholds)
    if len(ctx)!=ctxauth.get("development_context_row_count"):
        raise GateError("Development context count mismatch")

    # Development H4 membership by symbol/as_of.
    geom={}
    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["materialization_file"])
        if sha256_file(f)!=sm["materialization_sha256"]:
            raise GateError(f"{symbol}: H4 materialization SHA mismatch")
        for row in iter_jsonl(f):
            if row.get("partition")!="DEVELOPMENT":continue
            as_of=str(row["as_of"])[:10]
            if as_of>DEV_END or as_of not in ctx:continue
            b=row.get("nearest_structural_room_pct_bin")
            if b in ("GE_10PCT","5_10PCT"):
                geom[(symbol,as_of)]=b

    memberships={name:set() for name in PRESELECTED}
    for ident,b in geom.items():
        symbol,as_of=ident
        for name,spec in PRESELECTED.items():
            if b!=h4_bin_for_candidate(spec["candidate_id"]):continue
            if ctx[as_of].get(spec["regime_id"],False):
                memberships[name].add(ident)

    for name,s in memberships.items():
        if len(s)<MIN_DEV_CELL_COUNT:
            raise GateError(f"{name}: Development membership {len(s)} below fixed floor")

    # Pairwise redundancy.
    names=list(PRESELECTED)
    overlap_rows=[]
    near_duplicate_pairs=[]
    for i in range(len(names)):
        for j in range(i+1,len(names)):
            a,b=names[i],names[j]
            ja=jaccard(memberships[a],memberships[b])
            ca,cb=containment(memberships[a],memberships[b])
            nd=ja>=NEAR_DUPLICATE_JACCARD
            overlap_rows.append({
                "candidate_a":a,
                "candidate_b":b,
                "count_a":len(memberships[a]),
                "count_b":len(memberships[b]),
                "intersection_count":len(memberships[a]&memberships[b]),
                "union_count":len(memberships[a]|memberships[b]),
                "jaccard":ja,
                "containment_a_in_b":ca,
                "containment_b_in_a":cb,
                "near_duplicate":nd,
            })
            if nd:near_duplicate_pairs.append((a,b))

    # Collapse near-duplicates by frozen priority only; never by Validation or newly-scored returns.
    active=set(names)
    collapse_decisions=[]
    for a,b in near_duplicate_pairs:
        if a not in active or b not in active:continue
        pa=PRESELECTED[a]["priority"];pb=PRESELECTED[b]["priority"]
        keep=a if pa<pb else b
        drop=b if keep==a else a
        active.discard(drop)
        collapse_decisions.append({
            "pair":[a,b],
            "rule":"JACCARD_GE_0_90_THEN_KEEP_LOWER_FROZEN_PRIORITY_NUMBER",
            "kept":keep,
            "dropped":drop,
        })

    authorized={}
    for name in names:
        spec=PRESELECTED[name]
        if name in active:
            authorized[name]={
                "candidate_id":spec["candidate_id"],
                "regime_id":spec["regime_id"],
                "horizons":list(spec["horizons"]),
                "concept":spec["concept"],
                "development_membership_count":len(memberships[name]),
            }

    report={
        "version":VERSION,
        "status":"READY",
        "development_evaluation_sha256":sha256_file(ep),
        "regime_authority_sha256":sha256_file(rp),
        "context_authority_sha256":sha256_file(cp),
        "context_csv_sha256":sha256_file(cc),
        "h4_authority_sha256":sha256_file(hp),
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "development_end":DEV_END,
        "preselected_candidates":PRESELECTED,
        "near_duplicate_jaccard_threshold":NEAR_DUPLICATE_JACCARD,
        "pairwise_overlap":overlap_rows,
        "near_duplicate_pairs":[list(x) for x in near_duplicate_pairs],
        "collapse_decisions":collapse_decisions,
        "authorized_validation_scope":authorized,
        "unauthorized_validation_scope":[name for name in names if name not in active],
        "validation_gate_contract":{
            "only_authorized_validation_scope_may_be_scored":True,
            "candidate_definitions_may_not_change_after_this_gate":True,
            "regime_definitions_may_not_change_after_this_gate":True,
            "horizons_may_not_change_after_this_gate":True,
            "validation_results_may_not_expand_scope":True,
            "final_holdout_remains_sealed":True,
        },
        "governance":{
            "development_membership_only_for_redundancy":True,
            "validation_context_read":False,
            "validation_candidate_outcomes_read":False,
            "final_holdout_context_read":False,
            "final_holdout_candidate_outcomes_read":False,
            "new_candidate_scored":False,
            "threshold_search_or_optimization":False,
            "regime_search_or_optimization":False,
            "parameter_fitting":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_20_AUTHORIZED_REGIME_CONDITIONED_VALIDATION_ONLY_EVALUATION",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)

    csv_rows=[]
    for x in overlap_rows:
        csv_rows.append({"record_type":"PAIRWISE_OVERLAP",**x,
                         "candidate":"","decision":"","horizons":"","concept":"","development_membership_count":""})
    for name in names:
        spec=PRESELECTED[name]
        csv_rows.append({
            "record_type":"ADVANCEMENT",
            "candidate_a":"","candidate_b":"","count_a":"","count_b":"","intersection_count":"","union_count":"",
            "jaccard":"","containment_a_in_b":"","containment_b_in_a":"","near_duplicate":"",
            "candidate":name,
            "decision":"AUTHORIZED_VALIDATION" if name in active else "COLLAPSED_REDUNDANT",
            "horizons":",".join(map(str,spec["horizons"])) if name in active else "",
            "concept":spec["concept"],
            "development_membership_count":len(memberships[name]),
        })
    fields=list(csv_rows[0].keys())
    outc.parent.mkdir(parents=True,exist_ok=True)
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(csv_rows)

    print("=== M77.19.7.4.19 REGIME-CONDITIONED CANDIDATE ADVANCEMENT & REDUNDANCY GATE ===")
    print("status: READY")
    print(f"development_context_row_count: {len(ctx)}")
    for name in names:
        print(f"{name}: development_membership_count={len(memberships[name])}")
    for x in overlap_rows:
        print(f"overlap {x['candidate_a']} vs {x['candidate_b']}: "
              f"intersection={x['intersection_count']} union={x['union_count']} "
              f"jaccard={x['jaccard']} containment_a_in_b={x['containment_a_in_b']} "
              f"containment_b_in_a={x['containment_b_in_a']} near_duplicate={x['near_duplicate']}")
    print("near_duplicate_pairs:", [list(x) for x in near_duplicate_pairs])
    print("collapse_decisions:", collapse_decisions)
    print("authorized_validation_scope:", authorized)
    print("validation_context_read: False")
    print("validation_candidate_outcomes_read: False")
    print("final_holdout_context_read: False")
    print("final_holdout_candidate_outcomes_read: False")
    print("new_candidate_scored: False")
    print("threshold_search_or_optimization: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_20_AUTHORIZED_REGIME_CONDITIONED_VALIDATION_ONLY_EVALUATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
