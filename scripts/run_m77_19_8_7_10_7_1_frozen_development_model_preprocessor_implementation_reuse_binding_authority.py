#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.1-FROZEN-DEVELOPMENT-MODEL-PREPROCESSOR-IMPLEMENTATION-REUSE-BINDING-AUTHORITY-1.0"

MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"

class BindingError(RuntimeError): pass

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

def source_segment(text,node):
    try:return ast.get_source_segment(text,node)
    except Exception:return None

def scan_script(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    funcs=[]
    classes=[]
    imports=[]
    calls=[]
    assignments=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            src=source_segment(text,n) or ""
            low=(n.name+" "+src[:1500]).lower()
            tags=[]
            for needle,tag in (
                ("preprocess","PREPROCESS"),
                ("standardscaler","SCALER"),
                ("onehotencoder","ENCODER"),
                ("simpleimputer","IMPUTER"),
                ("logisticregression","MF1_LOGISTIC"),
                ("lbfgsb","MF2_LBFGSB"),
                ("spline","MF2_SPLINE"),
                ("monotonic","MF2_MONOTONIC"),
                ("balanced_accuracy","METRIC_BAL_ACC"),
                ("predict_proba","PREDICT_PROBA"),
                ("predict","PREDICT"),
                ("fit(","FIT_CALL"),
                ("transform(","TRANSFORM_CALL"),
            ):
                if needle in low:tags.append(tag)
            funcs.append({
                "name":n.name,
                "lineno":n.lineno,
                "end_lineno":getattr(n,"end_lineno",n.lineno),
                "arg_names":[a.arg for a in n.args.args],
                "tags":sorted(set(tags)),
            })
        elif isinstance(n,ast.ClassDef):
            classes.append({"name":n.name,"lineno":n.lineno})
        elif isinstance(n,(ast.Import,ast.ImportFrom)):
            imports.append({"lineno":n.lineno,"source":source_segment(text,n)})
        elif isinstance(n,ast.Call):
            src=source_segment(text,n) or ""
            low=src.lower()
            if any(x in low for x in ("fit(","transform(","predict","logistic","minimize","lbfg","spline","balanced_accuracy")):
                calls.append({"lineno":n.lineno,"source":src[:1000]})
        elif isinstance(n,(ast.Assign,ast.AnnAssign)):
            src=source_segment(text,n) or ""
            low=src.lower()
            if any(x in low for x in ("mf1","mf2","selected_config","spline","l2_penalty","logistic","preprocess")):
                assignments.append({"lineno":n.lineno,"source":src[:1200]})
    return {
        "path":str(path),
        "sha256":sha256_file(path),
        "function_count":len(funcs),
        "functions":funcs,
        "classes":classes,
        "imports":imports,
        "candidate_calls":calls,
        "candidate_assignments":assignments,
    }

def function_candidates(scan,tags):
    out=[]
    for f in scan["functions"]:
        if any(t in f["tags"] for t in tags):
            out.append(f)
    return out

# M77.19.8.7.10.7.1.1-MF2-SEMANTIC-AUTHORITY-SCHEMA-BINDING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-runtime-script",default="scripts/run_m77_19_8_7_4_mf2_runtime_mf3_elastic_net_quantile_solver_certification.py")
    ap.add_argument("--mf2-semantic-json",default="reports/m77_19_8_7_3_mf2_monotonic_sign_semantic_authority_mf3_solver_decision_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_1_frozen_development_model_preprocessor_implementation_reuse_binding_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_1_implementation_reuse_binding_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    pre=load_json(resolve(root,args.preregistration_json))
    if pre.get("status")!="READY" or pre.get("validation_scoring_authorized") is not True:
        raise BindingError("10.7 preregistration not READY/authorized")
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
            raise BindingError(f"10.7 governance changed: {k}={pre.get(k)!r}")

    mf1p=resolve(root,args.mf1_development_script)
    mf2p=resolve(root,args.mf2_development_script)
    mf2rp=resolve(root,args.mf2_runtime_script)
    for p in (mf1p,mf2p,mf2rp):
        if not p.exists():raise BindingError(f"required implementation script missing: {p}")

    scans={
        "mf1_development":scan_script(mf1p),
        "mf2_development":scan_script(mf2p),
        "mf2_runtime":scan_script(mf2rp),
    }

    mf1_model=function_candidates(scans["mf1_development"],{"MF1_LOGISTIC","PREDICT_PROBA","PREDICT"})
    mf1_pre=function_candidates(scans["mf1_development"],{"PREPROCESS","SCALER","ENCODER","IMPUTER","TRANSFORM_CALL"})
    mf2_model=function_candidates(scans["mf2_development"],{"MF2_LBFGSB","MF2_SPLINE","MF2_MONOTONIC","PREDICT"})
    mf2_pre=function_candidates(scans["mf2_development"],{"PREPROCESS","SCALER","ENCODER","IMPUTER","TRANSFORM_CALL"})
    mf2_runtime=function_candidates(scans["mf2_runtime"],{"MF2_LBFGSB","MF2_SPLINE","MF2_MONOTONIC"})

    # This is deliberately a binding census, not an authorization by name alone.
    # A later invocation-parity gate must prove the exact callable contract.
    candidates_found={
        "MF1_model_candidate_count":len(mf1_model),
        "MF1_preprocessor_candidate_count":len(mf1_pre),
        "MF2_model_candidate_count":len(mf2_model),
        "MF2_preprocessor_candidate_count":len(mf2_pre),
        "MF2_runtime_candidate_count":len(mf2_runtime),
    }
    enough_to_build_contract=(
        len(mf1_model)>0 and
        len(mf2_model)>0 and
        len(mf2_runtime)>0
    )

    semantic=load_json(resolve(root,args.mf2_semantic_json))
    if semantic.get("status")!="READY":
        raise BindingError("MF2 semantic authority not READY")
    mf2_semantic=semantic.get("MF2")
    if not isinstance(mf2_semantic,dict):
        raise BindingError("MF2 semantic authority block missing")
    required_mf2_semantic={
        "semantic_authority_certified": True,
        "outcomes_used_to_choose_signs": False,
        "validation_used_to_choose_signs": False,
        "field_level_monotonic_sign_map_materialized": True,
        "registered_column_count": 97,
        "constrained_column_count": 6,
        "unconstrained_column_count": 91,
    }
    unresolved_or_conflicting={
        k:{"expected":expected,"actual":mf2_semantic.get(k)}
        for k,expected in required_mf2_semantic.items()
        if mf2_semantic.get(k) != expected
    }
    if unresolved_or_conflicting:
        raise BindingError("MF2 semantic authority unresolved/conflicting: " + repr(unresolved_or_conflicting))
    # Runtime certification is intentionally NOT required from 7.3;
    # 7.3 predates runtime certification and is the semantic/sign authority only.
    if mf2_semantic.get("runtime_certified") is not False:
        raise BindingError("MF2 7.3 semantic authority runtime state changed unexpectedly")

    registry=[]
    for source_name,scan in scans.items():
        for f in scan["functions"]:
            if f["tags"]:
                registry.append({
                    "source":source_name,
                    "source_sha256":scan["sha256"],
                    "function":f["name"],
                    "lineno":f["lineno"],
                    "args":"|".join(f["arg_names"]),
                    "tags":"|".join(f["tags"]),
                })

    status="READY" if enough_to_build_contract else "BLOCKED_REUSABLE_IMPLEMENTATION_CANDIDATES_INCOMPLETE"
    report={
        "version":VERSION,
        "status":status,
        "preregistration_sha256":sha256_file(resolve(root,args.preregistration_json)),
        "source_scans":scans,
        "candidate_summary":candidates_found,
        "MF1_model_candidates":mf1_model,
        "MF1_preprocessor_candidates":mf1_pre,
        "MF2_model_candidates":mf2_model,
        "MF2_preprocessor_candidates":mf2_pre,
        "MF2_runtime_candidates":mf2_runtime,
        "MF2_semantic_authority_sha256":sha256_file(resolve(root,args.mf2_semantic_json)),
        "MF2_semantic_authority_resolution":{
            "semantic_authority_certified":mf2_semantic.get("semantic_authority_certified"),
            "outcomes_used_to_choose_signs":mf2_semantic.get("outcomes_used_to_choose_signs"),
            "validation_used_to_choose_signs":mf2_semantic.get("validation_used_to_choose_signs"),
            "field_level_monotonic_sign_map_materialized":mf2_semantic.get("field_level_monotonic_sign_map_materialized"),
            "registered_column_count":mf2_semantic.get("registered_column_count"),
            "constrained_column_count":mf2_semantic.get("constrained_column_count"),
            "unconstrained_column_count":mf2_semantic.get("unconstrained_column_count"),
            "runtime_certified_at_7_3":mf2_semantic.get("runtime_certified"),
        },
        "MF2_semantic_authority_schema_binding_certified":True,
        "reusable_implementation_candidates_sufficient":enough_to_build_contract,
        "exact_callable_invocation_contract_certified":False,
        "development_invocation_parity_certified":False,
        "validation_scoring_execution_authorized":False,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_EXACT_MF1_MF2_CALLABLE_INVOCATION_CONTRACT_AND_DEVELOPMENT_PARITY_HARNESS"
            if enough_to_build_contract else
            "REVIEW_M77_19_8_7_10_7_1_REUSABLE_IMPLEMENTATION_CANDIDATE_GAPS"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["source","source_sha256","function","lineno","args","tags"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in registry:w.writerow(r)

    print("=== M77.19.8.7.10.7.1 FROZEN DEVELOPMENT MODEL/PREPROCESSOR IMPLEMENTATION REUSE BINDING AUTHORITY ===")
    print("status:",status)
    for k,v in candidates_found.items():print(f"{k}: {v}")
    print("MF2_semantic_authority_schema_binding_certified: True")
    print("MF2_semantic_authority_certified:",mf2_semantic.get("semantic_authority_certified"))
    print("MF2_outcomes_used_to_choose_signs:",mf2_semantic.get("outcomes_used_to_choose_signs"))
    print("MF2_validation_used_to_choose_signs:",mf2_semantic.get("validation_used_to_choose_signs"))
    print("MF2_registered_column_count:",mf2_semantic.get("registered_column_count"))
    print("MF2_constrained_column_count:",mf2_semantic.get("constrained_column_count"))
    print("MF2_unconstrained_column_count:",mf2_semantic.get("unconstrained_column_count"))
    print("reusable_implementation_candidates_sufficient:",enough_to_build_contract)
    print("exact_callable_invocation_contract_certified: False")
    print("development_invocation_parity_certified: False")
    print("validation_scoring_execution_authorized: False")
    print("validation_scoring_performed: False")
    print("validation_preprocessor_refit_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("model_family_champion_selected: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
