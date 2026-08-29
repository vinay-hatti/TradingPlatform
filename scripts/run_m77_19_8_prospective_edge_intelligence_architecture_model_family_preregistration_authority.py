#!/usr/bin/env python3
"""
M77.19.8 — Prospective Edge Intelligence Architecture & Model-Family Preregistration Authority

Defines a materially different prospective-edge architecture after closure of
the heuristic bearish-filter research branch.

This milestone:
- reads only the M77.19.7.4.21 closure authority;
- does not train, fit, score, tune, or validate a model;
- does not read Development, Validation, or Final Holdout outcome rows;
- preregisters the architecture, targets, feature domains, model families,
  explainability requirements, and evaluation protocol.

Production remains unchanged.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.8-PROSPECTIVE-EDGE-INTELLIGENCE-ARCHITECTURE-MODEL-FAMILY-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_CLOSURE_VERSION="M77.19.7.4.21-PROSPECTIVE-BEARISH-EDGE-RESEARCH-CLOSURE-FINAL-HOLDOUT-PRESERVATION-AUTHORITY-1.0"
FINAL_HOLDOUT_START="2023-01-01"
HORIZONS=[5,10,20]

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
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

MODEL_FAMILIES=[
    {
        "id":"MF1_REGULARIZED_LOGISTIC_DIRECTION",
        "type":"INTERPRETABLE_LINEAR_PROBABILITY",
        "targets":["P_UP","P_DOWN"],
        "fit_separately_by_horizon":True,
        "regularization":"L2_OR_ELASTIC_NET_PREDECLARED_GRID_ONLY_IN_DEVELOPMENT",
        "explainability":"SIGNED_STANDARDIZED_COEFFICIENTS_AND_FEATURE_CONTRIBUTIONS",
        "black_box":False,
    },
    {
        "id":"MF2_MONOTONIC_GAM_DIRECTION",
        "type":"INTERPRETABLE_NONLINEAR_ADDITIVE_PROBABILITY",
        "targets":["P_UP","P_DOWN"],
        "fit_separately_by_horizon":True,
        "shape_constraints":"ONLY_WHERE_ECONOMIC_DIRECTION_IS_PREDECLARED",
        "explainability":"PER_FEATURE_SHAPE_FUNCTIONS_AND_ADDITIVE_CONTRIBUTIONS",
        "black_box":False,
    },
    {
        "id":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION",
        "type":"INTERPRETABLE_DISTRIBUTIONAL_RETURN",
        "targets":["Q10_RETURN","Q50_RETURN","Q90_RETURN"],
        "fit_separately_by_horizon":True,
        "regularization":"FIXED_ROBUST_LINEAR_QUANTILE_SPECIFICATION",
        "explainability":"SIGNED_COEFFICIENTS_BY_QUANTILE",
        "black_box":False,
    },
]

FEATURE_DOMAINS=[
    "PRICE_TREND_AND_MOMENTUM",
    "MULTITIMEFRAME_ALIGNMENT",
    "VOLATILITY_AND_RANGE",
    "SUPPORT_RESISTANCE_AND_STRUCTURE",
    "BREAKOUT_BREAKDOWN_STATE",
    "PARTICIPATION_AND_VOLUME",
    "MARKET_REGIME_AND_BREADTH",
    "RELATIVE_STRENGTH_VS_MARKET_AND_SECTOR",
    "DRAW_DOWN_AND_DISTANCE_FROM_EXTREMES",
    "STATE_TRANSITION_AND_PERSISTENCE",
]

TARGETS=[
    {
        "id":"ABSOLUTE_FORWARD_RETURN",
        "definition":"close[t+h]/close[t]-1",
        "horizons":HORIZONS,
        "use":"distributional return target",
    },
    {
        "id":"MARKET_RELATIVE_FORWARD_RETURN",
        "definition":"symbol_forward_return - SPY_forward_return over same sessions",
        "horizons":HORIZONS,
        "use":"market-neutral predictive edge target",
    },
    {
        "id":"DIRECTION_LABEL",
        "definition":"UP if forward_return>0, DOWN if forward_return<0; exact zero handled explicitly",
        "horizons":HORIZONS,
        "use":"probabilistic directional target",
    },
]

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--closure-json",default="reports/m77_19_7_4_21_prospective_bearish_edge_research_closure_final_holdout_preservation_authority.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_prospective_edge_intelligence_architecture_model_family_preregistration_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_model_family_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    cp=resolve(root,args.closure_json)
    closure=load_json(cp)
    if closure.get("version")!=EXPECTED_CLOSURE_VERSION or closure.get("status")!="READY":
        raise AuthorityError("M77.19.7.4.21 closure authority invalid")
    cs=closure.get("closure_state") or {}
    if cs.get("prospective_bearish_edge_research_branch")!="CLOSED_NO_CERTIFIED_CHAMPION":
        raise AuthorityError("closed bearish branch authority missing")
    if cs.get("further_filter_rescue_search_authorized") is not False:
        raise AuthorityError("filter rescue must remain prohibited")
    fh=closure.get("final_holdout_preservation") or {}
    if fh.get("remains_pristine_for_materially_different_future_architecture") is not True:
        raise AuthorityError("Final Holdout preservation authority missing")

    report={
        "version":VERSION,
        "status":"READY",
        "closure_authority_sha256":sha256_file(cp),
        "architecture":{
            "name":"PROSPECTIVE_EDGE_INTELLIGENCE",
            "materially_different_from_closed_bearish_filter_branch":True,
            "symmetric_bullish_and_bearish_prediction":True,
            "distributional_not_state_label_reinterpretation":True,
            "multi_horizon":HORIZONS,
            "descriptive_state_input_only_not_prediction_target":True,
            "separate_market_relative_edge":True,
            "separate_absolute_return_distribution":True,
            "calibration_required_before_any_production_use":True,
        },
        "targets":TARGETS,
        "feature_domains":FEATURE_DOMAINS,
        "model_families":MODEL_FAMILIES,
        "feature_governance":{
            "point_in_time_only":True,
            "future_information_for_features_prohibited":True,
            "closed_hypothesis_identity_as_feature_prohibited":True,
            "symbol_identity_as_predictive_feature_prohibited":True,
            "raw_ticker_one_hot_prohibited":True,
            "corporate_action_adjustment_provenance_required":True,
            "missingness_must_be_explicit":True,
            "feature_standardization_fit_on_development_only":True,
        },
        "training_protocol":{
            "development_partition_end":"2017-12-31",
            "validation_partition_start":"2018-01-01",
            "validation_partition_end":"2022-12-31",
            "final_holdout_start":FINAL_HOLDOUT_START,
            "walk_forward_training_required":True,
            "purge_forward_horizon_overlap_required":True,
            "symbol_cluster_robust_uncertainty_required":True,
            "year_block_robust_uncertainty_required":True,
            "model_family_selection_development_only":True,
            "hyperparameter_selection_development_only":True,
            "validation_used_once_for_family_certification":True,
            "final_holdout_used_once_only_after_validation_certification":True,
        },
        "evaluation_protocol":{
            "direction_metrics":["BrierScore","LogLoss","ROC_AUC_DIAGNOSTIC","DirectionalAccuracy"],
            "calibration_metrics":["ReliabilityCurve","CalibrationSlope","CalibrationIntercept","ECE"],
            "return_metrics":["MAE_Q50","PinballLoss_Q10_Q50_Q90","MedianRealizedReturnByPredictedEdgeBin"],
            "baseline_comparisons":["UNCONDITIONAL_DIRECTION_RATE","PREVIOUS_PERIOD_DIRECTION","MARKET_DRIFT_BASELINE"],
            "economic_metrics":["ExpectedDirectionalReturn","PayoffRatio","TailLoss","MarketRelativeReturn"],
            "minimum_validation_requirements_predeclare_before_training":True,
        },
        "explainability_contract":{
            "per_prediction_feature_contributions_required":True,
            "global_feature_effects_required":True,
            "sign_stability_across_walk_forward_folds_required":True,
            "feature_effect_direction_conflicts_flagged":True,
            "black_box_model_family_authorized":False,
        },
        "research_prohibitions":{
            "automatic_bearish_signal_inversion":False,
            "reuse_closed_filter_hypotheses_as_candidate_model":False,
            "final_holdout_peeking":False,
            "validation_driven_feature_creation":False,
            "validation_driven_threshold_search":False,
            "production_auto_promotion":False,
        },
        "execution_state":{
            "features_materialized":False,
            "models_trained":False,
            "models_scored":False,
            "validation_opened_for_new_architecture":False,
            "final_holdout_opened":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_1_POINT_IN_TIME_PROSPECTIVE_EDGE_FEATURE_AUTHORITY",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)

    rows=[]
    for m in MODEL_FAMILIES:
        rows.append({
            "model_family_id":m["id"],
            "type":m["type"],
            "targets":"|".join(m["targets"]),
            "fit_separately_by_horizon":m["fit_separately_by_horizon"],
            "black_box":m["black_box"],
            "explainability":m["explainability"],
        })
    outc.parent.mkdir(parents=True,exist_ok=True)
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys()))
        w.writeheader();w.writerows(rows)

    print("=== M77.19.8 PROSPECTIVE EDGE INTELLIGENCE ARCHITECTURE & MODEL-FAMILY PREREGISTRATION AUTHORITY ===")
    print("status: READY")
    print("architecture: PROSPECTIVE_EDGE_INTELLIGENCE")
    print("materially_different_from_closed_bearish_filter_branch: True")
    print("symmetric_bullish_and_bearish_prediction: True")
    print("distributional_not_state_label_reinterpretation: True")
    print("horizons:", HORIZONS)
    print("targets:", [x["id"] for x in TARGETS])
    print("feature_domains:", FEATURE_DOMAINS)
    print("model_families:", [x["id"] for x in MODEL_FAMILIES])
    print("black_box_model_family_authorized: False")
    print("development_only_model_family_selection: True")
    print("validation_opened_for_new_architecture: False")
    print("final_holdout_opened: False")
    print("models_trained: False")
    print("production_model_change_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_1_POINT_IN_TIME_PROSPECTIVE_EDGE_FEATURE_AUTHORITY")
    print("report:",outj)
    print("csv:",outc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
