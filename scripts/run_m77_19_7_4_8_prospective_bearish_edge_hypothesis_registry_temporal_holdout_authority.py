#!/usr/bin/env python3
"""
M77.19.7.4.8 — Prospective Bearish Edge Hypothesis Registry &
Temporal Holdout Authority

This package freezes candidate hypotheses and temporal partitions BEFORE any
candidate performance evaluation.

It does not compute directional accuracy, forward returns, payoff ratios,
candidate rankings, thresholds, fitted weights, calibrators, or champion scores.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.8-PROSPECTIVE-BEARISH-EDGE-HYPOTHESIS-REGISTRY-TEMPORAL-HOLDOUT-AUTHORITY-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_SYMBOLS=602

PARTITIONS=(
    ("DEVELOPMENT", None, "2017-12-31"),
    ("VALIDATION", "2018-01-01", "2022-12-31"),
    ("FINAL_HOLDOUT", "2023-01-01", None),
)

# Hypotheses are frozen conceptually here. They are not scored by this package.
HYPOTHESES=(
    {
        "id":"H1_FRESH_DOWNSIDE_TRANSITION",
        "name":"Fresh downside transition",
        "intent":"Test whether newly bearish transitions retain more prospective downside edge than mature bearish states.",
        "required_observables":[
            "native_direction","previous_direction","bearish_streak_observations",
            "prior_10_session_return","prior_20_session_return",
            "drawdown_from_prior_63_session_high"
        ],
        "predeclared_semantics":[
            "current native direction is BEARISH or STRONG_BEARISH",
            "transitioned_into_bearish is TRUE",
            "exclude already-deep extension overlays in later evaluation"
        ],
    },
    {
        "id":"H2_BREAKDOWN_INITIATION",
        "name":"Breakdown initiation",
        "intent":"Test whether initiation/setup has more prospective edge than mature confirmed breakdown.",
        "required_observables":[
            "breakout.state","native_direction","bearish_streak_observations"
        ],
        "predeclared_semantics":[
            "prefer BREAKDOWN_SETUP / newly lost structure evidence",
            "compare separately against BREAKDOWN_CONFIRMED",
            "do not invert BREAKDOWN_CONFIRMED"
        ],
    },
    {
        "id":"H3_CONTINUATION_WITHOUT_EXHAUSTION",
        "name":"Continuation without exhaustion",
        "intent":"Test bearish continuation only when exhaustion-like state is absent.",
        "required_observables":[
            "participation.state","breakout.state","prior_10_session_return",
            "prior_20_session_return","drawdown_from_prior_63_session_high",
            "bearish_streak_observations"
        ],
        "predeclared_semantics":[
            "exclude CAPITULATION",
            "exclude mature BREAKDOWN_CONFIRMED in late lifecycle",
            "exclude large prior-decline/deep-drawdown exhaustion overlays"
        ],
    },
    {
        "id":"H4_REMAINING_STRUCTURAL_DOWNSIDE_ROOM",
        "name":"Remaining structural downside room",
        "intent":"Test whether remaining distance to defensible support/demand destinations is prospective evidence.",
        "required_observables":[
            "current_reference_price","support_levels","demand_zones",
            "ATR_or_native_volatility_context","native_direction","bearish_streak_observations"
        ],
        "predeclared_semantics":[
            "measure remaining downside room rather than bearish severity alone",
            "use native point-in-time structural levels only",
            "no future structure or realized target information"
        ],
    },
)

class AuthorityError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:
        return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():
        return p
    if not p.is_absolute():
        q=root/p
        if q.exists():
            return q
    for anchor in ("reports","research_data","data"):
        if anchor in p.parts:
            q=root.joinpath(*p.parts[p.parts.index(anchor):])
            if q.exists():
                return q
    return p

def iter_jsonl_gz(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except Exception as exc:
                raise AuthorityError(f"{path}:{i}: invalid JSONL") from exc

def partition_for(as_of:str)->str:
    d=date.fromisoformat(as_of[:10])
    if d<=date(2017,12,31):
        return "DEVELOPMENT"
    if d<=date(2022,12,31):
        return "VALIDATION"
    return "FINAL_HOLDOUT"

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True)
            fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--semantic-authority-json",default="reports/m77_19_7_4_7_bearish_state_vs_prospective_edge_semantic_decomposition.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_8_prospective_bearish_edge_hypothesis_registry_temporal_holdout_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_8_symbol_partition_authority.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.replay_authority_json)
    op=resolve(root,args.outcome_authority_json)
    sp=resolve(root,args.semantic_authority_json)

    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:
        raise AuthorityError("replay authority SHA mismatch")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:
        raise AuthorityError("outcome authority SHA mismatch")

    replay=load_json(rp)
    outcome=load_json(op)
    semantic=load_json(sp)

    if replay.get("status")!="READY":
        raise AuthorityError("replay authority not READY")
    if outcome.get("status")!="READY":
        raise AuthorityError("outcome authority not READY")
    if semantic.get("status")!="READY":
        raise AuthorityError("M77.19.7.4.7 semantic decomposition not READY")
    if replay.get("successful_symbol_cadence_replay_count")!=EXPECTED_SYMBOLS:
        raise AuthorityError("replay symbol count mismatch")
    if outcome.get("successful_symbol_evaluation_count")!=EXPECTED_SYMBOLS:
        raise AuthorityError("outcome symbol count mismatch")

    symbol_rows=[]
    aggregate_partition_counts=Counter()
    aggregate_symbol_counts=Counter()
    first_dates={}
    last_dates={}

    weekly=[x for x in replay.get("symbols") or [] if x.get("cadence")=="WEEKLY"]
    if len(weekly)!=EXPECTED_SYMBOLS:
        raise AuthorityError(f"expected {EXPECTED_SYMBOLS} WEEKLY replay symbols; got {len(weekly)}")

    for meta in sorted(weekly,key=lambda x:str(x["symbol"])):
        symbol=str(meta["symbol"])
        result=resolve(root,meta["result_file"])
        if not result.is_file():
            raise AuthorityError(f"{symbol}: replay result missing")
        if sha256_file(result)!=meta["result_sha256"]:
            raise AuthorityError(f"{symbol}: replay result SHA mismatch")

        counts=Counter()
        dates=[]
        for row in iter_jsonl_gz(result):
            status=row.get("status")
            if status=="NOT_ELIGIBLE_NATIVE":
                continue
            if status!="REPLAYED":
                raise AuthorityError(f"{symbol}: unexpected replay status {status!r}")
            as_of=str(row["as_of"])[:10]
            dates.append(as_of)
            counts[partition_for(as_of)]+=1

        if not dates:
            raise AuthorityError(f"{symbol}: no REPLAYED observations")

        first_dates[symbol]=min(dates)
        last_dates[symbol]=max(dates)

        rec={
            "symbol":symbol,
            "first_replayed_as_of":min(dates),
            "last_replayed_as_of":max(dates),
            "development_observation_count":counts["DEVELOPMENT"],
            "validation_observation_count":counts["VALIDATION"],
            "final_holdout_observation_count":counts["FINAL_HOLDOUT"],
            "development_eligible":counts["DEVELOPMENT"]>0,
            "validation_eligible":counts["VALIDATION"]>0,
            "final_holdout_eligible":counts["FINAL_HOLDOUT"]>0,
        }
        symbol_rows.append(rec)
        for p in ("DEVELOPMENT","VALIDATION","FINAL_HOLDOUT"):
            aggregate_partition_counts[p]+=counts[p]
            if counts[p]>0:
                aggregate_symbol_counts[p]+=1

    registry={
        "version":VERSION,
        "status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "semantic_decomposition_authority_sha256":sha256_file(sp),
        "successful_symbol_count":EXPECTED_SYMBOLS,
        "temporal_partitions":[
            {"name":"DEVELOPMENT","start":None,"end":"2017-12-31","performance_use":"candidate-development-only"},
            {"name":"VALIDATION","start":"2018-01-01","end":"2022-12-31","performance_use":"independent-validation"},
            {"name":"FINAL_HOLDOUT","start":"2023-01-01","end":None,"performance_use":"untouched-final-certification"},
        ],
        "hypothesis_registry":list(HYPOTHESES),
        "symbol_specific_window_policy":{
            "use_each_symbol_certified_history_only":True,
            "force_common_23_year_start":False,
            "predecessor_successor_auto_concatenation":False,
            "synthetic_backfill":False,
            "partition_membership_requires_actual_replayed_observation":True,
        },
        "partition_authority":{
            p:{
                "replayed_observation_count":aggregate_partition_counts[p],
                "eligible_symbol_count":aggregate_symbol_counts[p],
            } for p in ("DEVELOPMENT","VALIDATION","FINAL_HOLDOUT")
        },
        "global_replay_window":{
            "first_replayed_as_of":min(first_dates.values()),
            "last_replayed_as_of":max(last_dates.values()),
        },
        "candidate_evaluation_contract":{
            "development_may_be_used_for_candidate_definition_refinement":True,
            "validation_may_be_used_for_candidate_accept_reject":True,
            "final_holdout_may_not_be_used_for_candidate_revision":True,
            "final_holdout_single_pass_intent":True,
            "minimum_acceptance_dimensions":[
                "positive_median_bearish_directional_return",
                "accuracy_above_predeclared_baseline",
                "adequate_sample_size",
                "cross_symbol_consistency",
                "cross_era_consistency",
                "validation_confirmation",
                "final_holdout_confirmation",
            ],
            "exact_numeric_acceptance_thresholds_fitted_here":False,
        },
        "performance_computation":{
            "candidate_accuracy_computed":False,
            "candidate_forward_returns_computed":False,
            "candidate_ranking_computed":False,
            "candidate_champion_selected":False,
        },
        "governance":{
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "calibrator_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "future_feature_leakage":False,
            "database_access":"NONE",
            "polygon_api_queried":False,
            "price_history_table_used":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_9_DEVELOPMENT_ONLY_PROSPECTIVE_BEARISH_EDGE_CANDIDATE_EVALUATION",
    }

    outj=Path(args.output_json)
    outc=Path(args.output_csv)
    if not outj.is_absolute():
        outj=root/outj
    if not outc.is_absolute():
        outc=root/outc
    atomic_json(outj,registry)

    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(symbol_rows[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields)
        w.writeheader()
        w.writerows(symbol_rows)

    print("=== M77.19.7.4.8 PROSPECTIVE BEARISH EDGE HYPOTHESIS REGISTRY & TEMPORAL HOLDOUT AUTHORITY ===")
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOLS}")
    print(f"semantic_decomposition_authority_sha256: {sha256_file(sp)}")
    for p in ("DEVELOPMENT","VALIDATION","FINAL_HOLDOUT"):
        x=registry["partition_authority"][p]
        print(f"{p}: eligible_symbols={x['eligible_symbol_count']} replayed_observations={x['replayed_observation_count']}")
    print(f"global_first_replayed_as_of: {registry['global_replay_window']['first_replayed_as_of']}")
    print(f"global_last_replayed_as_of: {registry['global_replay_window']['last_replayed_as_of']}")
    print("hypotheses:", [h["id"] for h in HYPOTHESES])
    print("candidate_accuracy_computed: False")
    print("candidate_forward_returns_computed: False")
    print("candidate_champion_selected: False")
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_9_DEVELOPMENT_ONLY_PROSPECTIVE_BEARISH_EDGE_CANDIDATE_EVALUATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
