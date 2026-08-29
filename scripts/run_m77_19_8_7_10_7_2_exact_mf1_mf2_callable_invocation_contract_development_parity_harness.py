#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, csv, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.8.7.10.7.2-EXACT-MF1-MF2-CALLABLE-INVOCATION-CONTRACT-DEVELOPMENT-PARITY-HARNESS-1.0"
MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=(5,10,20)

class ContractError(RuntimeError): pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
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

def src(text,node):
    try:
        return ast.get_source_segment(text,node) or ""
    except Exception:
        return ""

def callable_census(path:Path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    funcs=[]
    top_calls=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            body=src(text,node)
            low=(node.name+"\n"+body).lower()
            tags=[]
            for needle,tag in (
                ("logisticregression","LOGISTIC"),
                ("predict_proba","PREDICT_PROBA"),
                ("balanced_accuracy","BALANCED_ACCURACY"),
                ("standardscaler","SCALER"),
                ("onehotencoder","ENCODER"),
                ("simpleimputer","IMPUTER"),
                ("preprocess","PREPROCESS"),
                ("transform(","TRANSFORM"),
                ("fit(","FIT"),
                ("minimize(","MINIMIZE"),
                ("l-bfgs-b","LBFGSB"),
                ("lbfgsb","LBFGSB"),
                ("spline","SPLINE"),
                ("monotonic","MONOTONIC"),
                ("selected_config","SELECTED_CONFIG"),
                ("checkpoint","CHECKPOINT"),
            ):
                if needle in low:
                    tags.append(tag)
            funcs.append({
                "name":node.name,
                "lineno":node.lineno,
                "end_lineno":getattr(node,"end_lineno",node.lineno),
                "args":[a.arg for a in node.args.args],
                "kwonlyargs":[a.arg for a in node.args.kwonlyargs],
                "defaults_count":len(node.args.defaults),
                "tags":sorted(set(tags)),
                "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
            })
        elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
            top_calls.append({"lineno":node.lineno,"source":src(text,node)[:1000]})
    return {
        "script_sha256":sha256_file(path),
        "functions":funcs,
        "top_level_calls":top_calls,
    }

def rank(funcs,family):
    ranked=[]
    for f in funcs:
        # Orchestration/dependency functions cannot certify exact model invocation.
        if f["name"] in {"main","require_ml"}:
            continue
        tags=set(f["tags"])
        score=0
        reasons=[]
        if family==MF1:
            for tag,pts in (("LOGISTIC",8),("PREDICT_PROBA",6),("BALANCED_ACCURACY",3),
                            ("PREPROCESS",4),("TRANSFORM",3),("SCALER",2),("ENCODER",2),("IMPUTER",2)):
                if tag in tags:
                    score+=pts;reasons.append(tag)
        else:
            for tag,pts in (("MONOTONIC",8),("SPLINE",7),("LBFGSB",7),("MINIMIZE",5),
                            ("BALANCED_ACCURACY",3),("PREPROCESS",4),("TRANSFORM",3),("SCALER",2)):
                if tag in tags:
                    score+=pts;reasons.append(tag)
        # Family-specific model semantics are mandatory. Metrics or generic
        # preprocessing helpers alone cannot certify model invocation reuse.
        if family==MF1:
            family_model_semantics=bool(tags & {"LOGISTIC","PREDICT_PROBA"})
        else:
            family_model_semantics=bool(tags & {"MONOTONIC","SPLINE","LBFGSB","MINIMIZE"})
        if score and family_model_semantics:
            ranked.append({**f,"score":score,"reasons":reasons,"family_model_semantics":True})
    return sorted(ranked,key=lambda x:(-x["score"],x["lineno"]))

def selected_dev_rows(report:dict,family:str):
    rows=[]
    # Recursively search dictionaries/lists for objects carrying family/horizon/selected_config.
    def walk(x):
        if isinstance(x,dict):
            fam=x.get("family")
            h=x.get("horizon")
            cfg=x.get("selected_config") or x.get("config")
            if fam==family and h in HORIZONS and isinstance(cfg,dict):
                rows.append({
                    "family":family,
                    "horizon":h,
                    "selected_config":cfg,
                    "mean_walk_forward_balanced_accuracy":x.get("mean_walk_forward_balanced_accuracy"),
                    "fold_count":x.get("fold_count"),
                })
            for v in x.values():
                walk(v)
        elif isinstance(x,list):
            for v in x:
                walk(v)
    walk(report)
    # De-dupe by horizon/config.
    seen=set();out=[]
    for r in rows:
        k=(r["horizon"],json.dumps(r["selected_config"],sort_keys=True))
        if k not in seen:
            seen.add(k);out.append(r)
    return out

# M77.19.8.7.10.7.2.1-MF2-EXPLICIT-CALLABLE-AND-CONFIG-PARITY-HARDENING
# M77.19.8.7.10.7.2.2-FAMILY-SPECIFIC-MODEL-CALLABLE-CONTRACT-HARDENING
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--reuse-binding-json",default="reports/m77_19_8_7_10_7_1_frozen_development_model_preprocessor_implementation_reuse_binding_authority.json")
    ap.add_argument("--preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf1-development-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_exact_mf1_mf2_callable_invocation_contract_development_parity_harness.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_callable_contract_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    binding=load_json(resolve(root,args.reuse_binding_json))
    pre=load_json(resolve(root,args.preregistration_json))
    if binding.get("status")!="READY" or binding.get("reusable_implementation_candidates_sufficient") is not True:
        raise ContractError("10.7.1 reuse binding not READY/sufficient")
    if binding.get("validation_scoring_execution_authorized") is not False:
        raise ContractError("Validation scoring execution unexpectedly already authorized")
    if pre.get("status")!="READY" or pre.get("validation_scoring_authorized") is not True:
        raise ContractError("10.7 preregistration not READY")
    for k in ("validation_model_refit_authorized","validation_model_retuning_authorized",
              "model_family_champion_selection_authorized","final_holdout_open_authorized"):
        if pre.get(k) is not False:
            raise ContractError(f"10.7 governance changed: {k}")

    mf1_script=resolve(root,args.mf1_development_script)
    mf2_script=resolve(root,args.mf2_development_script)
    mf1_json=resolve(root,args.mf1_development_json)
    mf2_json=resolve(root,args.mf2_development_json)

    for p in (mf1_script,mf2_script,mf1_json,mf2_json):
        if not p.exists():
            raise ContractError(f"required Development artifact missing: {p}")

    c1=callable_census(mf1_script)
    c2=callable_census(mf2_script)
    r1=rank(c1["functions"],MF1)
    r2=rank(c2["functions"],MF2)

    if not r1:
        raise ContractError("no MF1 reusable callable candidates found")
    if not r2:
        raise ContractError("no MF2 reusable callable candidates found")

    # Bind exact highest-ranked callable candidates, but do NOT execute Validation.
    mf1_primary=r1[0]
    mf2_primary=r2[0]

    # Development evidence parity here means frozen selected Development evidence
    # remains exactly the same evidence that 10.7 preregistered for Validation.
    d1=load_json(mf1_json)
    d2=load_json(mf2_json)
    dev1=selected_dev_rows(d1,MF1)

    frozen1=pre.get("frozen_MF1_selected_configs") or {}
    frozen2=pre.get("frozen_MF2_selected_configs") or {}

    # MF1 report may expose selected evidence recursively; require exact config parity
    # where discoverable. MF2's 10.7 frozen configs are compared with its Development
    # authority when explicit selected_configs_by_horizon/frozen configs exist.
    mf1_config_parity={}
    for h in HORIZONS:
        cfg=frozen1.get(str(h)) or frozen1.get(h)
        matches=[x for x in dev1 if x["horizon"]==h and x["selected_config"]==cfg]
        mf1_config_parity[str(h)]=bool(matches)

    mf2_source_cfg={}
    def walk_mf2_cfg(x):
        if isinstance(x,dict):
            fam=x.get("family")
            h=x.get("horizon")
            cfg=x.get("selected_config") or x.get("config")
            if fam==MF2 and h in HORIZONS and isinstance(cfg,dict):
                mf2_source_cfg[str(h)]=cfg
            for key in ("selected_configs_by_horizon","frozen_MF2_selected_configs","selected_configs"):
                v=x.get(key)
                if isinstance(v,dict):
                    for hh in HORIZONS:
                        cc=v.get(str(hh)) or v.get(hh)
                        if isinstance(cc,dict):
                            mf2_source_cfg[str(hh)]=cc
            for v in x.values():
                walk_mf2_cfg(v)
        elif isinstance(x,list):
            for v in x:
                walk_mf2_cfg(v)
    walk_mf2_cfg(d2)

    mf2_config_parity={}
    for h in HORIZONS:
        frozen=frozen2.get(str(h)) or frozen2.get(h)
        source=mf2_source_cfg.get(str(h))
        mf2_config_parity[str(h)]=(source==frozen) if source is not None else None

    # Callable contract certification is source/signature binding only.
    exact_callable_contract=(
        mf1_primary["name"] not in {"main","require_ml","balanced_accuracy"} and
        mf2_primary["name"] not in {"main","require_ml","balanced_accuracy"} and
        mf1_primary.get("family_model_semantics") is True and
        mf2_primary.get("family_model_semantics") is True and
        bool(set(mf1_primary.get("tags") or []) & {"LOGISTIC","PREDICT_PROBA"}) and
        bool(set(mf2_primary.get("tags") or []) & {"MONOTONIC","SPLINE","LBFGSB","MINIMIZE"}) and
        bool(mf1_primary["source_sha256"]) and
        bool(mf2_primary["source_sha256"]) and
        c1["script_sha256"]==binding["source_scans"]["mf1_development"]["sha256"] and
        c2["script_sha256"]==binding["source_scans"]["mf2_development"]["sha256"]
    )

    # Development parity is config/evidence parity, not a new model refit.
    mf1_all_parity=all(mf1_config_parity.values())
    # Missing/None MF2 evidence is a BLOCK, never a pass.
    mf2_all_parity=all(mf2_config_parity.get(str(h)) is True for h in HORIZONS)
    development_parity=exact_callable_contract and mf1_all_parity and mf2_all_parity

    registry=[]
    for fam,ranked in ((MF1,r1),(MF2,r2)):
        for i,f in enumerate(ranked,1):
            registry.append({
                "family":fam,
                "rank":i,
                "function":f["name"],
                "lineno":f["lineno"],
                "end_lineno":f["end_lineno"],
                "args":"|".join(f["args"]),
                "tags":"|".join(f["tags"]),
                "score":f["score"],
                "source_sha256":f["source_sha256"],
                "selected_primary":i==1,
            })

    status="READY" if development_parity else "BLOCKED_DEVELOPMENT_INVOCATION_PARITY_NOT_CERTIFIED"
    report={
        "version":VERSION,
        "status":status,
        "reuse_binding_sha256":sha256_file(resolve(root,args.reuse_binding_json)),
        "preregistration_sha256":sha256_file(resolve(root,args.preregistration_json)),
        "MF1_script_sha256":c1["script_sha256"],
        "MF2_script_sha256":c2["script_sha256"],
        "MF1_primary_callable":mf1_primary,
        "MF2_primary_callable":mf2_primary,
        "MF1_candidate_count":len(r1),
        "MF2_candidate_count":len(r2),
        "MF1_frozen_config_parity":mf1_config_parity,
        "MF2_frozen_config_parity":mf2_config_parity,
        "MF2_all_horizons_explicit_config_parity":mf2_all_parity,
        "orchestration_callables_excluded":["main","require_ml"],
        "metric_only_callables_excluded":["balanced_accuracy"],
        "MF1_required_model_tags":["LOGISTIC","PREDICT_PROBA"],
        "MF2_required_model_tags":["MONOTONIC","SPLINE","LBFGSB","MINIMIZE"],
        "MF1_primary_has_family_model_semantics":mf1_primary.get("family_model_semantics") is True,
        "MF2_primary_has_family_model_semantics":mf2_primary.get("family_model_semantics") is True,
        "exact_callable_invocation_contract_certified":exact_callable_contract,
        "development_invocation_parity_certified":development_parity,
        "development_model_refit_performed":False,
        "development_retuning_performed":False,
        "validation_scoring_execution_authorized":development_parity,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_3_FROZEN_MF1_MF2_VALIDATION_SCORING_EXECUTION_WITH_DEVELOPMENT_ONLY_FIT"
            if development_parity else
            "REVIEW_M77_19_8_7_10_7_2_DEVELOPMENT_INVOCATION_PARITY_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(registry[0].keys()))
        w.writeheader();w.writerows(registry)

    print("=== M77.19.8.7.10.7.2 EXACT MF1/MF2 CALLABLE INVOCATION CONTRACT & DEVELOPMENT PARITY HARNESS ===")
    print("status:",status)
    print("MF1_primary_callable:",mf1_primary["name"])
    print("MF1_primary_callable_source_sha256:",mf1_primary["source_sha256"])
    print("MF2_primary_callable:",mf2_primary["name"])
    print("MF2_primary_callable_source_sha256:",mf2_primary["source_sha256"])
    print("MF1_frozen_config_parity:",mf1_config_parity)
    print("MF2_frozen_config_parity:",mf2_config_parity)
    print("MF2_all_horizons_explicit_config_parity:",mf2_all_parity)
    print("orchestration_callables_excluded: [\'main\', \'require_ml\']")
    print("metric_only_callables_excluded: [\'balanced_accuracy\']")
    print("MF1_primary_tags:",mf1_primary.get("tags"))
    print("MF2_primary_tags:",mf2_primary.get("tags"))
    print("MF1_primary_has_family_model_semantics:",mf1_primary.get("family_model_semantics") is True)
    print("MF2_primary_has_family_model_semantics:",mf2_primary.get("family_model_semantics") is True)
    print("exact_callable_invocation_contract_certified:",exact_callable_contract)
    print("development_invocation_parity_certified:",development_parity)
    print("development_model_refit_performed: False")
    print("development_retuning_performed: False")
    print("validation_scoring_execution_authorized:",development_parity)
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
