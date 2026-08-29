#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"
EXPECTED_85_VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"

FOLDS=[
    {"fold_id":"WF1","train_end":"2008-12-31","test_start":"2009-01-01","test_end":"2010-12-31"},
    {"fold_id":"WF2","train_end":"2010-12-31","test_start":"2011-01-01","test_end":"2012-12-31"},
    {"fold_id":"WF3","train_end":"2012-12-31","test_start":"2013-01-01","test_end":"2014-12-31"},
    {"fold_id":"WF4","train_end":"2014-12-31","test_start":"2015-01-01","test_end":"2016-12-31"},
    {"fold_id":"WF5","train_end":"2016-12-31","test_start":"2017-01-01","test_end":"2017-12-31"},
]

MODEL_FAMILIES={
    "MF1_REGULARIZED_LOGISTIC_DIRECTION":{
        "target":"T_DIRECTION",
        "horizons":[5,10,20],
        "solver_family":"L2_LOGISTIC",
        "fixed_grid":{"C":[0.01,0.1,1.0,10.0]},
        "class_weight":"NONE",
        "multiclass_policy":"DROP_ZERO_LABEL_ROWS_THEN_BINARY_UP_VS_DOWN",
    },
    "MF2_MONOTONIC_GAM_DIRECTION":{
        "target":"T_DIRECTION",
        "horizons":[5,10,20],
        "basis":"UNIVARIATE_MONOTONIC_SPLINES",
        "fixed_grid":{"spline_knots":[4,6,8],"l2_penalty":[0.1,1.0,10.0]},
        "monotonic_constraints":"ONLY_WHERE_PREDECLARED_DOMAIN_SIGN_EXISTS_OTHERWISE_UNCONSTRAINED",
        "multiclass_policy":"DROP_ZERO_LABEL_ROWS_THEN_BINARY_UP_VS_DOWN",
    },
    "MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION":{
        "target":"T_ABS_RET",
        "horizons":[5,10,20],
        "quantiles":[0.1,0.25,0.5,0.75,0.9],
        "fixed_grid":{"l1_ratio":[0.0,0.5,1.0],"alpha":[0.0001,0.001,0.01]},
        "secondary_target":"T_REL_SPY_RET",
    },
}

class GateError(RuntimeError): pass

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(path):
    with Path(path).open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root,raw):
    p=Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def column_name(fid,path):
    safe=path.replace(".","__").replace("[","_").replace("]","")
    return f"{fid}__{safe}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_6_training_feature_column_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    tp=resolve(root,args.target_authority_json)
    ta=load_json(tp)
    if ta.get("version")!=EXPECTED_85_VERSION or ta.get("status")!="READY":
        raise GateError("M77.19.8.5 authority invalid")
    if ta.get("target_matrix",{}).get("feature_observation_count")!=303689:
        raise GateError("Development observation authority mismatch")
    gov=ta.get("governance") or {}
    if gov.get("validation_outcomes_opened") is not False or gov.get("final_holdout_outcomes_opened") is not False:
        raise GateError("Validation/Final Holdout must remain closed")

    sw=ta.get("structured_feature_whitelist") or {}
    f012=sw.get("F012_whitelisted_paths") or []
    f051=sw.get("F051_whitelisted_paths") or []
    if len(f012)!=42 or len(f051)!=30:
        raise GateError(f"unexpected structured whitelist counts: F012={len(f012)} F051={len(f051)}")

    structured_columns=[]
    for fid,paths in (("F012",f012),("F051",f051)):
        for p in paths:
            structured_columns.append({
                "feature_id":fid,
                "source_path":p,
                "column_name":column_name(fid,p),
                "materialization":"SCALAR_EXACT_PATH",
                "categorical_encoding":"ONE_HOT_IF_STRING_FIXED_FROM_DEVELOPMENT_TRAIN_FOLD_ONLY",
                "numeric_scaling":"STANDARDIZE_FROM_TRAIN_FOLD_ONLY",
                "missingness":"EXPLICIT_MISSING_INDICATOR_PLUS_NO_GLOBAL_IMPUTATION",
            })

    base_feature_contract={
        "existing_base_feature_ids":[
            "F001","F002","F003","F010","F011","F020","F021","F030","F031","F032","F033",
            "F040","F050","F060","F061","F062","F063","F064","F065","F070","F080","F081","F090","F091"
        ],
        "structured_source_ids":["F012","F051"],
        "blocked_feature_ids":["F071"],
        "F071_excluded_from_training":True,
        "symbol_identity_excluded":True,
        "closed_hypothesis_identity_excluded":True,
    }

    encoding={
        "numeric":{
            "fit_scope":"TRAIN_FOLD_ONLY",
            "standardization":"MEAN_STD",
            "zero_variance":"DROP_WITHIN_FOLD_AND_RECORD",
            "missing_policy":"MISSING_INDICATOR_PLUS_TRAIN_FOLD_MEDIAN",
        },
        "categorical":{
            "fit_scope":"TRAIN_FOLD_ONLY",
            "encoding":"ONE_HOT",
            "unknown_policy":"EXPLICIT_UNKNOWN_CATEGORY",
            "rare_category_collapse":"DISABLED",
        },
        "boolean":{"encoding":"0_1","missing_policy":"EXPLICIT_MISSING_INDICATOR"},
        "structured":{
            "free_form_flattening":False,
            "only_8_5_whitelisted_paths":True,
        },
    }

    walk_forward={
        "folds":FOLDS,
        "expanding_window":True,
        "test_windows_non_overlapping":True,
        "purge_sessions_by_horizon":{"5":5,"10":10,"20":20},
        "embargo_sessions_after_test":0,
        "purge_rule":"REMOVE_TRAIN_ROWS_WHOSE_TARGET_SESSION_REACHES_OR_EXCEEDS_TEST_START",
        "selection_scope":"DEVELOPMENT_ONLY",
        "validation_period_used":False,
        "final_holdout_used":False,
    }

    selection={
        "primary_direction_metric":"BALANCED_ACCURACY",
        "secondary_direction_metrics":["LOG_LOSS","Brier_SCORE","ROC_AUC"],
        "return_metrics":["PINBALL_LOSS","MEDIAN_ABSOLUTE_ERROR","DIRECTIONAL_ACCURACY_FROM_MEDIAN_SIGN"],
        "family_selection_rule":"LOWEST_MEAN_WALK_FORWARD_PRIMARY_LOSS_WITH_COMPLEXITY_TIE_BREAK",
        "tie_break":"PREFER_SIMPLER_MODEL_WITHIN_1_STANDARD_ERROR",
        "horizon_specific_models":True,
        "global_feature_selection_search":False,
        "interaction_search":False,
        "threshold_search":False,
        "validation_used_for_selection":False,
        "final_holdout_used_for_selection":False,
    }

    report={
        "version":VERSION,
        "status":"READY",
        "target_authority_sha256":sha256_file(tp),
        "development_authority":{
            "feature_observation_count":303689,
            "development_end":DEV_END,
            "structured_F012_path_count":len(f012),
            "structured_F051_path_count":len(f051),
            "structured_materialized_column_count":len(structured_columns),
        },
        "training_feature_contract":base_feature_contract,
        "structured_columns":structured_columns,
        "encoding_and_missingness":encoding,
        "walk_forward_preregistration":walk_forward,
        "model_family_preregistration":MODEL_FAMILIES,
        "selection_and_metrics":selection,
        "execution_state":{
            "structured_training_matrix_materialized":False,
            "training_preprocessors_fit":False,
            "models_trained":False,
            "development_walk_forward_scored":False,
            "model_family_selected":False,
            "validation_opened":False,
            "final_holdout_opened":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_7_DEVELOPMENT_ONLY_STRUCTURED_TRAINING_MATRIX_AND_WALK_FORWARD_MODEL_FAMILY_EVALUATION",
    }

    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        fields=["feature_id","source_path","column_name","materialization","categorical_encoding","numeric_scaling","missingness"]
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(structured_columns)

    print("=== M77.19.8.6 STRUCTURED FEATURE MATERIALIZATION & DEVELOPMENT MODEL-TRAINING PREREGISTRATION GATE ===")
    print("status: READY")
    print("development_feature_observation_count: 303689")
    print("F012_whitelisted_paths:",len(f012))
    print("F051_whitelisted_paths:",len(f051))
    print("structured_materialized_column_count:",len(structured_columns))
    print("F071_excluded_from_training: True")
    print("walk_forward_fold_count:",len(FOLDS))
    print("walk_forward_folds:",[x["fold_id"] for x in FOLDS])
    print("purge_sessions_by_horizon:",walk_forward["purge_sessions_by_horizon"])
    print("model_families:",list(MODEL_FAMILIES))
    print("validation_period_used_for_selection: False")
    print("final_holdout_used_for_selection: False")
    print("structured_training_matrix_materialized: False")
    print("models_trained: False")
    print("development_walk_forward_scored: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_DEVELOPMENT_ONLY_STRUCTURED_TRAINING_MATRIX_AND_WALK_FORWARD_MODEL_FAMILY_EVALUATION")
    print("report:",oj)
    print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
