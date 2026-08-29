#!/usr/bin/env python3
"""
M77.19.7.4.15 — Regime-Conditioned Prospective Edge Research Authority

Freezes the next research framework after M77.19.7.4.14 established
Development-to-Validation instability.

This package DOES NOT evaluate a new prospective bearish candidate.
It defines the regime taxonomy, evidence contract, and holdout governance for
future regime-conditioned research.

Final Holdout >= 2023-01-01 remains sealed.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.7.4.15-REGIME-CONDITIONED-PROSPECTIVE-EDGE-RESEARCH-AUTHORITY-1.0"
EXPECTED_INSTABILITY_VERSION="M77.19.7.4.14-DEVELOPMENT-VALIDATION-REGIME-SHIFT-EDGE-INSTABILITY-FORENSICS-1.0"

FINAL_HOLDOUT_START="2023-01-01"

# Predeclared regime dimensions. No thresholds are optimized here.
REGIME_DIMENSIONS=(
    {
        "id":"MARKET_DRIFT",
        "intent":"Separate persistent upward, neutral, and downward market drift environments.",
        "source_authority":"frozen point-in-time market/index history only",
        "future_data_allowed":False,
        "categories":["UP_DRIFT","NEUTRAL_DRIFT","DOWN_DRIFT"],
        "thresholds_fitted_here":False,
    },
    {
        "id":"VOLATILITY",
        "intent":"Separate low, normal, and elevated realized-volatility environments.",
        "source_authority":"point-in-time native/frozen volatility evidence only",
        "future_data_allowed":False,
        "categories":["LOW_VOL","NORMAL_VOL","HIGH_VOL"],
        "thresholds_fitted_here":False,
    },
    {
        "id":"TREND_REGIME",
        "intent":"Separate broad market trend regimes without using candidate outcomes.",
        "source_authority":"point-in-time market/trend intelligence or frozen index history",
        "future_data_allowed":False,
        "categories":["UPTREND","SIDEWAYS","DOWNTREND"],
        "thresholds_fitted_here":False,
    },
    {
        "id":"BREADTH_REGIME",
        "intent":"Separate broad participation from narrow/weak participation.",
        "source_authority":"point-in-time breadth evidence only when historically available",
        "future_data_allowed":False,
        "categories":["BROAD","MIXED","WEAK"],
        "thresholds_fitted_here":False,
    },
    {
        "id":"BEAR_MARKET_CONTEXT",
        "intent":"Identify major market drawdown context separately from ordinary bearish signals.",
        "source_authority":"point-in-time index drawdown state only",
        "future_data_allowed":False,
        "categories":["NORMAL","CORRECTION","BEAR_MARKET"],
        "thresholds_fitted_here":False,
    },
)

RESEARCH_CONTRACT={
    "descriptive_state_and_prospective_edge_remain_separate":True,
    "candidate_outcome_may_not_define_regime":True,
    "validation_failure_may_not_be_used_to_relabel_regimes":True,
    "regime_thresholds_must_be_predeclared_before_candidate_scoring":True,
    "regime_combinations_must_be_predeclared_before_candidate_scoring":True,
    "minimum_cell_count_must_be_predeclared":True,
    "no_symbol_specific_rule":True,
    "no_historical_answer_leakage":True,
    "no_final_holdout_access":True,
}

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

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent); os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True); fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--instability-json",default="reports/m77_19_7_4_14_development_validation_regime_shift_edge_instability_forensics.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_15_regime_conditioned_prospective_edge_research_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_15_regime_dimension_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    ip=resolve(root,args.instability_json)
    instability=load_json(ip)

    if instability.get("version")!=EXPECTED_INSTABILITY_VERSION or instability.get("status")!="READY":
        raise AuthorityError("M77.19.7.4.14 instability authority invalid")
    findings=instability.get("forensic_findings") or {}
    if findings.get("all_authorized_candidates_failed_validation") is not True:
        raise AuthorityError("expected all authorized candidates to have failed validation")
    if findings.get("development_validation_instability_present") is not True:
        raise AuthorityError("expected Development/Validation instability")
    if findings.get("final_holdout_remains_sealed") is not True:
        raise AuthorityError("Final Holdout must remain sealed upstream")

    report={
        "version":VERSION,
        "status":"READY",
        "instability_authority_sha256":sha256_file(ip),
        "instability_conclusion_frozen":{
            "all_authorized_candidates_failed_validation":True,
            "development_validation_instability_present":True,
            "existing_candidate_family_retired_from_certification":True,
            "final_holdout_remains_sealed":True,
        },
        "regime_dimensions":list(REGIME_DIMENSIONS),
        "research_contract":RESEARCH_CONTRACT,
        "future_research_sequence":[
            "MATERIALIZE_POINT_IN_TIME_REGIME_CONTEXT_WITHOUT_CANDIDATE_OUTCOMES",
            "FREEZE_REGIME_THRESHOLDS_AND_COMBINATIONS",
            "DEVELOPMENT_ONLY_REGIME_CONDITIONED_EVALUATION",
            "INDEPENDENT_VALIDATION_ONLY_IF_DEVELOPMENT_GATE_PASSES",
            "FINAL_HOLDOUT_ONLY_IF_VALIDATION_GATE_PASSES",
        ],
        "final_holdout_policy":{
            "start":FINAL_HOLDOUT_START,
            "opened":False,
            "candidate_scoring_authorized":False,
            "regime_threshold_fitting_authorized":False,
            "diagnostic_peeking_authorized":False,
        },
        "governance":{
            "new_candidate_scored":False,
            "new_candidate_selected":False,
            "regime_thresholds_fitted":False,
            "regime_combinations_searched":False,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_16_POINT_IN_TIME_REGIME_CONTEXT_MATERIALIZATION_AUTHORITY",
    }

    outj=Path(args.output_json); outc=Path(args.output_csv)
    if not outj.is_absolute(): outj=root/outj
    if not outc.is_absolute(): outc=root/outc
    atomic_json(outj,report)

    rows=[]
    for d in REGIME_DIMENSIONS:
        rows.append({
            "id":d["id"],
            "intent":d["intent"],
            "source_authority":d["source_authority"],
            "categories":"|".join(d["categories"]),
            "future_data_allowed":d["future_data_allowed"],
            "thresholds_fitted_here":d["thresholds_fitted_here"],
        })
    outc.parent.mkdir(parents=True,exist_ok=True)
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("=== M77.19.7.4.15 REGIME-CONDITIONED PROSPECTIVE EDGE RESEARCH AUTHORITY ===")
    print("status: READY")
    print("all_authorized_candidates_failed_validation: True")
    print("development_validation_instability_present: True")
    print("existing_candidate_family_retired_from_certification: True")
    print("regime_dimensions:", [d["id"] for d in REGIME_DIMENSIONS])
    print("new_candidate_scored: False")
    print("regime_thresholds_fitted: False")
    print("regime_combinations_searched: False")
    print("final_holdout_opened: False")
    print("final_holdout_candidate_scoring_authorized: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_16_POINT_IN_TIME_REGIME_CONTEXT_MATERIALIZATION_AUTHORITY")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
