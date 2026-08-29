#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, os, tempfile
from pathlib import Path

VERSION="M77.19.8.7.2-MF2-MF3-IMPLEMENTATION-AUTHORITY-1.0"
EXPECTED_87_VERSION="M77.19.8.7-DEVELOPMENT-ONLY-STRUCTURED-TRAINING-MATRIX-WALK-FORWARD-MODEL-FAMILY-EVALUATION-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"

class AuthorityError(RuntimeError):
    pass

def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def load_json(p: Path):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

def resolve(root: Path, p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def atomic_json(path: Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp")
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True)
            f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--development-eval-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_2_mf2_mf3_implementation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_2_mf2_mf3_implementation_registry.csv")
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    ep=resolve(root,a.development_eval_json)
    gp=resolve(root,a.training_gate_json)
    ev=load_json(ep)
    gate=load_json(gp)

    if ev.get("version")!=EXPECTED_87_VERSION or ev.get("status")!="READY":
        raise AuthorityError("M77.19.8.7 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":
        raise AuthorityError("M77.19.8.6 gate invalid")
    if ev.get("MF2_status")!="BLOCKED_PENDING_CERTIFIED_MONOTONIC_SIGN_MAP_AND_RUNTIME":
        raise AuthorityError("unexpected MF2 upstream state")
    if ev.get("MF3_status")!="BLOCKED_PENDING_CERTIFIED_ELASTIC_NET_QUANTILE_LINEAR_SOLVER":
        raise AuthorityError("unexpected MF3 upstream state")

    # Preserve MF1 evidence exactly; no retuning.
    mf1=[
        x for x in (ev.get("development_selected_configs") or [])
        if x.get("family")=="MF1_REGULARIZED_LOGISTIC_DIRECTION"
    ]
    expected={(5,10.0),(10,1.0),(20,0.1)}
    actual={(x.get("horizon"),x.get("selected_config",{}).get("C")) for x in mf1}
    if actual!=expected:
        raise AuthorityError(f"MF1 selected Development configs changed unexpectedly: {actual}")

    # MF2 runtime discovery is informational only. A runtime does not authorize signs.
    pygam_available=importlib.util.find_spec("pygam") is not None
    mf2={
        "family":"MF2_MONOTONIC_GAM_DIRECTION",
        "runtime_pygam_available":pygam_available,
        "field_level_monotonic_sign_map_materialized":False,
        "sign_map_source":"REQUIRES_EX_ANTE_FEATURE_SEMANTIC_AUTHORITY_NOT_OUTCOME_FITTING",
        "implementation_certified":False,
        "development_scoring_authorized":False,
        "retirement_authorized":False,
        "reason":"MONOTONIC_SIGN_MAP_NOT_YET_AUTHORIZED",
    }

    mf3_spec=(gate.get("model_family_preregistration") or {}).get("MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION") or {}
    grid=mf3_spec.get("fixed_grid") or {}
    if set(grid)!={"l1_ratio","alpha"}:
        raise AuthorityError(f"MF3 preregistered grid changed: {grid}")

    mf3={
        "family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION",
        "required_alpha_grid":grid.get("alpha"),
        "required_l1_ratio_grid":grid.get("l1_ratio"),
        "required_quantiles":mf3_spec.get("quantiles"),
        "sklearn_quantile_regressor_contract_compatible":False,
        "certified_solver_available":False,
        "implementation_certified":False,
        "development_scoring_authorized":False,
        "retirement_authorized":False,
        "reason":"NO_CERTIFIED_SOLVER_IMPLEMENTING_PREREGISTERED_ALPHA_X_L1_RATIO_QUANTILE_OBJECTIVE",
    }

    rows=[
        {
            "family":mf2["family"],
            "implementation_certified":False,
            "development_scoring_authorized":False,
            "retirement_authorized":False,
            "reason":mf2["reason"],
        },
        {
            "family":mf3["family"],
            "implementation_certified":False,
            "development_scoring_authorized":False,
            "retirement_authorized":False,
            "reason":mf3["reason"],
        },
    ]

    report={
        "version":VERSION,
        "status":"READY",
        "development_eval_sha256":sha256_file(ep),
        "training_gate_sha256":sha256_file(gp),
        "MF1_development_selected_configs_preserved":mf1,
        "MF1_retuning_authorized":False,
        "MF2":mf2,
        "MF3":mf3,
        "all_preregistered_model_families_development_evaluated":False,
        "model_family_comparison_complete":False,
        "validation_open_authorized":False,
        "final_holdout_open_authorized":False,
        "preregistration_change_authorized":False,
        "silent_model_family_substitution_authorized":False,
        "production_model_change_authorized":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_3_MF2_MONOTONIC_SIGN_SEMANTIC_AUTHORITY_AND_MF3_SOLVER_DECISION_GATE",
    }

    oj=resolve(root,a.output_json)
    oc=resolve(root,a.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("=== M77.19.8.7.2 MF2 / MF3 IMPLEMENTATION AUTHORITY ===")
    print("status: READY")
    print("MF1_development_selected_configs_preserved:",mf1)
    print("MF1_retuning_authorized: False")
    print("MF2_runtime_pygam_available:",pygam_available)
    print("MF2_implementation_certified: False")
    print("MF2_development_scoring_authorized: False")
    print("MF3_sklearn_quantile_regressor_contract_compatible: False")
    print("MF3_implementation_certified: False")
    print("MF3_development_scoring_authorized: False")
    print("all_preregistered_model_families_development_evaluated: False")
    print("model_family_comparison_complete: False")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("preregistration_change_authorized: False")
    print("silent_model_family_substitution_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_3_MF2_MONOTONIC_SIGN_SEMANTIC_AUTHORITY_AND_MF3_SOLVER_DECISION_GATE")
    print("report:",oj)
    print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
