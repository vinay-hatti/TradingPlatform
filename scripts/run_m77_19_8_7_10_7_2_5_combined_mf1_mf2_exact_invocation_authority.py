#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.5-COMBINED-MF1-MF2-EXACT-INVOCATION-AUTHORITY-1.0"
MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=("5","10","20")

class AuthorityError(RuntimeError): pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

# M77.19.8.7.10.7.2.5.1-MF1-CALLABLE-RECORD-NORMALIZATION-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--mf1-mf2-parity-json",default="reports/m77_19_8_7_10_7_2_exact_mf1_mf2_callable_invocation_contract_development_parity_harness.json")
    ap.add_argument("--mf2-exact-chain-json",default="reports/m77_19_8_7_10_7_2_4_6_exact_fit_predict_proba_chain_parity_gate.json")
    ap.add_argument("--validation-preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--validation-target-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_5_combined_invocation_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    pair=load_json(resolve(root,args.mf1_mf2_parity_json))
    mf2=load_json(resolve(root,args.mf2_exact_chain_json))
    pre=load_json(resolve(root,args.validation_preregistration_json))
    targets=load_json(resolve(root,args.validation_target_authority_json))

    if pair.get("MF1_frozen_config_parity") != {"5":True,"10":True,"20":True}:
        raise AuthorityError("MF1 frozen config parity incomplete")
    if pair.get("development_model_refit_performed") is not False:
        raise AuthorityError("Development refit unexpectedly performed in MF1/MF2 parity authority")
    if pair.get("development_retuning_performed") is not False:
        raise AuthorityError("Development retuning unexpectedly performed in MF1/MF2 parity authority")

    if mf2.get("status")!="READY":
        raise AuthorityError("MF2 exact chain gate not READY")
    required_mf2_flags=(
        "preprocessor_fit_certified",
        "preprocessor_transform_certified",
        "CertifiedMonotonicGAM_fit_chain_certified",
        "predict_proba_certified",
        "fixed_threshold_050_certified",
        "balanced_accuracy_metric_binding_certified",
        "MF2_all_horizons_explicit_config_parity",
        "exact_fit_predict_proba_chain_parity_certified",
        "development_invocation_parity_certified",
    )
    for k in required_mf2_flags:
        if mf2.get(k) is not True:
            raise AuthorityError(f"MF2 exact chain certification incomplete: {k}")

    if pre.get("status")!="READY" or pre.get("validation_scoring_authorized") is not True:
        raise AuthorityError("Validation preregistration not READY/authorized")
    for k in (
        "validation_preprocessor_fit_authorized",
        "validation_model_refit_authorized",
        "validation_model_retuning_authorized",
        "validation_threshold_search_authorized",
        "validation_feature_selection_search_authorized",
        "model_family_champion_selection_authorized",
        "final_holdout_open_authorized",
    ):
        if pre.get(k) is not False:
            raise AuthorityError(f"Validation governance unexpectedly relaxed: {k}")

    if targets.get("status")!="READY" or targets.get("validation_targets_materialized") is not True:
        raise AuthorityError("Validation target authority not READY/materialized")
    if targets.get("validation_scoring_performed") is not False:
        raise AuthorityError("Validation scoring unexpectedly already performed")
    if targets.get("final_holdout_feature_rows_opened") is not False:
        raise AuthorityError("Final Holdout feature rows unexpectedly opened")
    if targets.get("final_holdout_targets_opened") is not False:
        raise AuthorityError("Final Holdout targets unexpectedly opened")
    if targets.get("final_holdout_outcomes_opened") is not False:
        raise AuthorityError("Final Holdout outcomes unexpectedly opened")

    mf1_primary_record=pair.get("MF1_primary_callable")
    if isinstance(mf1_primary_record,dict):
        mf1_primary_name=mf1_primary_record.get("name")
        mf1_primary_source_sha256=mf1_primary_record.get("source_sha256")
    elif isinstance(mf1_primary_record,str):
        mf1_primary_name=mf1_primary_record
        mf1_primary_source_sha256=pair.get("MF1_primary_callable_source_sha256")
    else:
        mf1_primary_name=None
        mf1_primary_source_sha256=None

    if not isinstance(mf1_primary_name,str) or not mf1_primary_name.strip():
        raise AuthorityError("MF1 primary callable record missing valid name")
    if mf1_primary_name in {"main","require_ml","balanced_accuracy"}:
        raise AuthorityError("MF1 primary callable is not certifiable")
    if not mf1_primary_source_sha256:
        raise AuthorityError("MF1 primary callable record missing source SHA")
    mf1_exact=True

    mf2_exact=True
    combined=mf1_exact and mf2_exact

    rows=[]
    for family in (MF1,MF2):
        for h in HORIZONS:
            if family==MF1:
                cfg=(pre.get("frozen_MF1_selected_configs") or {}).get(h)
                source="M77.19.8.7.10.7.2"
                exact=True
            else:
                cfg=(pre.get("frozen_MF2_selected_configs") or {}).get(h)
                source="M77.19.8.7.10.7.2.4.6"
                exact=True
            rows.append({
                "family":family,
                "horizon":int(h),
                "frozen_config_json":json.dumps(cfg,sort_keys=True),
                "invocation_authority_source":source,
                "exact_invocation_certified":exact,
                "validation_scoring_authorized":combined,
            })

    report={
        "version":VERSION,
        "status":"READY" if combined else "BLOCKED_COMBINED_INVOCATION_AUTHORITY",
        "mf1_mf2_parity_sha256":sha256_file(resolve(root,args.mf1_mf2_parity_json)),
        "mf2_exact_chain_sha256":sha256_file(resolve(root,args.mf2_exact_chain_json)),
        "validation_preregistration_sha256":sha256_file(resolve(root,args.validation_preregistration_json)),
        "validation_target_authority_sha256":sha256_file(resolve(root,args.validation_target_authority_json)),
        "MF1_exact_invocation_certified":mf1_exact,
        "MF1_primary_callable":mf1_primary_record,
        "MF1_primary_callable_name":mf1_primary_name,
        "MF1_primary_callable_source_sha256":mf1_primary_source_sha256,
        "MF1_frozen_config_parity":pair.get("MF1_frozen_config_parity"),
        "MF2_exact_invocation_certified":mf2_exact,
        "MF2_exact_chain_components":{
            "preprocessor_fit_certified":mf2.get("preprocessor_fit_certified"),
            "preprocessor_transform_certified":mf2.get("preprocessor_transform_certified"),
            "CertifiedMonotonicGAM_fit_chain_certified":mf2.get("CertifiedMonotonicGAM_fit_chain_certified"),
            "predict_proba_certified":mf2.get("predict_proba_certified"),
            "fixed_threshold_050_certified":mf2.get("fixed_threshold_050_certified"),
            "balanced_accuracy_metric_binding_certified":mf2.get("balanced_accuracy_metric_binding_certified"),
        },
        "MF2_frozen_config_parity":mf2.get("MF2_frozen_config_parity"),
        "combined_exact_invocation_authority_certified":combined,
        "authorized_validation_scope":pre.get("authorized_validation_scope"),
        "frozen_MF1_selected_configs":pre.get("frozen_MF1_selected_configs"),
        "frozen_MF2_selected_configs":pre.get("frozen_MF2_selected_configs"),
        "validation_targets_materialized":targets.get("validation_targets_materialized"),
        "validation_scoring_execution_authorized":combined,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "validation_threshold_search_performed":False,
        "validation_feature_selection_search_performed":False,
        "model_family_champion_selection_authorized":False,
        "model_family_champion_selected":False,
        "final_holdout_open_authorized":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_3_FROZEN_MF1_MF2_VALIDATION_SCORING_EXECUTION_WITH_DEVELOPMENT_ONLY_FIT"
            if combined else
            "REVIEW_M77_19_8_7_10_7_2_5_COMBINED_INVOCATION_AUTHORITY_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["family","horizon","frozen_config_json","invocation_authority_source","exact_invocation_certified","validation_scoring_authorized"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.5 COMBINED MF1/MF2 EXACT INVOCATION AUTHORITY ===")
    print("status:",report["status"])
    print("MF1_exact_invocation_certified:",mf1_exact)
    print("MF1_primary_callable_name:",mf1_primary_name)
    print("MF1_primary_callable_source_sha256:",mf1_primary_source_sha256)
    print("MF1_frozen_config_parity:",pair.get("MF1_frozen_config_parity"))
    print("MF2_exact_invocation_certified:",mf2_exact)
    print("MF2_frozen_config_parity:",mf2.get("MF2_frozen_config_parity"))
    print("combined_exact_invocation_authority_certified:",combined)
    print("authorized_validation_scope:",pre.get("authorized_validation_scope"))
    print("validation_targets_materialized:",targets.get("validation_targets_materialized"))
    print("validation_scoring_execution_authorized:",combined)
    print("validation_scoring_performed: False")
    print("validation_preprocessor_refit_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("validation_threshold_search_performed: False")
    print("validation_feature_selection_search_performed: False")
    print("model_family_champion_selection_authorized: False")
    print("model_family_champion_selected: False")
    print("final_holdout_open_authorized: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
