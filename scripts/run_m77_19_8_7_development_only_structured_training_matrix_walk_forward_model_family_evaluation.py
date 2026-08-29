#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.8.7-DEVELOPMENT-ONLY-STRUCTURED-TRAINING-MATRIX-WALK-FORWARD-MODEL-FAMILY-EVALUATION-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"
EXPECTED_85_VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"
HORIZONS=[5,10,20]

class EvalError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def iter_jsonl_gz(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise EvalError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def get_path(obj:Any,path:str):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def scalar(v):
    if v is None:return None
    if isinstance(v,(bool,int,float,str)):return v
    return None

def flatten_base_features(values:dict[str,Any]):
    out={}
    for fid,v in sorted(values.items()):
        if fid=="F071":continue
        if isinstance(v,dict):
            # Only F070 is an already-preregistered structured two-scalar object.
            if fid!="F070":continue
            for k,x in sorted(v.items()):
                if isinstance(x,(bool,int,float,str)) or x is None:
                    out[f"{fid}__{k}"]=x
        elif isinstance(v,(bool,int,float,str)) or v is None:
            out[fid]=v
    return out

def build_structured(replay_profile:dict[str,Any], gate:dict[str,Any]):
    cols={}
    for rec in gate.get("structured_columns") or []:
        fid=rec["feature_id"]; source=rec["source_path"]; col=rec["column_name"]
        payload = replay_profile.get("timeframe_states") if fid=="F012" else replay_profile.get("institutional_volume")
        cols[col]=scalar(get_path(payload or {},source))
    return cols

def require_ml():
    try:
        import numpy as np
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import balanced_accuracy_score, log_loss, brier_score_loss, roc_auc_score, mean_pinball_loss, median_absolute_error
    except Exception as exc:
        raise EvalError("M77.19.8.7 requires numpy and scikit-learn in the project environment") from exc
    return locals()

def build_preprocessor(rows, feature_cols, ml):
    np=ml["np"]; ColumnTransformer=ml["ColumnTransformer"];Pipeline=ml["Pipeline"]
    SimpleImputer=ml["SimpleImputer"];OneHotEncoder=ml["OneHotEncoder"];StandardScaler=ml["StandardScaler"]
    numeric=[];categorical=[]
    for c in feature_cols:
        vals=[r.get(c) for r in rows if r.get(c) is not None]
        if vals and all(isinstance(v,(bool,int,float)) and not isinstance(v,str) for v in vals):numeric.append(c)
        else:categorical.append(c)
    num_pipe=Pipeline([
        ("imputer",SimpleImputer(strategy="median",add_indicator=True)),
        ("scale",StandardScaler()),
    ])
    cat_pipe=Pipeline([
        ("imputer",SimpleImputer(strategy="constant",fill_value="__MISSING__")),
        ("onehot",OneHotEncoder(handle_unknown="ignore",sparse_output=True)),
    ])
    transformers=[]
    if numeric:transformers.append(("num",num_pipe,numeric))
    if categorical:transformers.append(("cat",cat_pipe,categorical))
    if not transformers:raise EvalError("no model features available")
    return ColumnTransformer(transformers,remainder="drop"),numeric,categorical

def dict_matrix(rows,cols,ml):
    np=ml["np"]
    # sklearn ColumnTransformer accepts dataframe more reliably than list-of-dicts.
    try:
        import pandas as pd
    except Exception as exc:
        raise EvalError("M77.19.8.7 requires pandas in the project environment") from exc
    return pd.DataFrame([{c:r.get(c) for c in cols} for r in rows],columns=cols)

def mf2_available():
    try:
        from pygam import LogisticGAM, s
        return True
    except Exception:
        return False

def evaluate_mf1(train_rows,test_rows,feature_cols,target_key,grid,ml,progress_prefix=""):
    LogisticRegression=ml["LogisticRegression"];balanced_accuracy_score=ml["balanced_accuracy_score"]
    log_loss=ml["log_loss"];brier_score_loss=ml["brier_score_loss"];roc_auc_score=ml["roc_auc_score"]
    Xtr=dict_matrix(train_rows,feature_cols,ml);Xte=dict_matrix(test_rows,feature_cols,ml)
    ytr=[1 if r[target_key]=="UP" else 0 for r in train_rows];yte=[1 if r[target_key]=="UP" else 0 for r in test_rows]
    results=[]
    from sklearn.pipeline import Pipeline
    for C in grid["C"]:
        print(f"{progress_prefix} MF1 C={C} START train={len(train_rows)} test={len(test_rows)}",flush=True)
        prep,nums,cats=build_preprocessor(train_rows,feature_cols,ml)
        # sklearn >=1.8 deprecates explicit penalty='l2'. l1_ratio=0 preserves L2 semantics.
        model=Pipeline([("prep",prep),("model",LogisticRegression(C=C,l1_ratio=0,solver="liblinear",max_iter=2000,random_state=77))])
        model.fit(Xtr,ytr)
        prob=model.predict_proba(Xte)[:,1];pred=(prob>=0.5).astype(int)
        rec={"C":C,"balanced_accuracy":float(balanced_accuracy_score(yte,pred)),"log_loss":float(log_loss(yte,prob,labels=[0,1])),"brier_score":float(brier_score_loss(yte,prob))}
        try:rec["roc_auc"]=float(roc_auc_score(yte,prob))
        except Exception:rec["roc_auc"]=None
        results.append(rec)
        print(f"{progress_prefix} MF1 C={C} DONE balanced_accuracy={rec['balanced_accuracy']:.6f}",flush=True)
    return results

def evaluate_mf3(train_rows,test_rows,feature_cols,target_key,grid,quantiles,ml,progress_prefix=""):
    """Fail closed: sklearn QuantileRegressor cannot implement preregistered l1_ratio grid.

    M77.19.8.6 froze alpha AND l1_ratio. Silently dropping l1_ratio changes the
    registered model family and invalidates evidence. A separately certified scalable
    elastic-net quantile-linear implementation is required before MF3 may be scored.
    """
    if "l1_ratio" not in grid or "alpha" not in grid:
        raise EvalError("MF3 preregistered grid missing alpha/l1_ratio authority")
    print(f"{progress_prefix} MF3 BLOCKED: solver contract does not implement frozen l1_ratio grid",flush=True)
    return [{
        "status":"BLOCKED_SOLVER_CONTRACT_NOT_CERTIFIED",
        "reason":"SKLEARN_QUANTILE_REGRESSOR_HAS_ALPHA_BUT_NO_L1_RATIO;_PREREGISTERED_MF3_REQUIRES_ALPHA_AND_L1_RATIO",
        "preregistered_alpha":grid["alpha"],
        "preregistered_l1_ratio":grid["l1_ratio"],
        "quantiles":quantiles,
    }]

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--feature-matrix-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_walk_forward_model_family_evidence.csv")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_walk_forward_checkpoint.json")
    ap.add_argument("--resume",action="store_true")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    gp=resolve(root,args.training_gate_json);tp=resolve(root,args.target_authority_json)
    fr=resolve(root,args.feature_matrix_root);tr=resolve(root,args.target_root);rr=resolve(root,args.replay_root)
    gate=load_json(gp);target_auth=load_json(tp)
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise EvalError("M77.19.8.6 gate invalid")
    if target_auth.get("version")!=EXPECTED_85_VERSION or target_auth.get("status")!="READY":raise EvalError("M77.19.8.5 target authority invalid")
    if gate.get("execution_state",{}).get("validation_opened") is not False or gate.get("execution_state",{}).get("final_holdout_opened") is not False:
        raise EvalError("Validation/Final Holdout gate invalid")

    feature_files={p.name[:-9]:p for p in fr.glob("*.jsonl.gz")}
    target_files={p.name[:-9]:p for p in tr.glob("*.jsonl.gz")}
    replay_files={p.name[:-9]:p for p in (rr/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(feature_files)!=524 or len(target_files)!=524:raise EvalError("expected 524 Development feature/target files")

    rows=[]
    all_feature_cols=set()
    for symbol in sorted(feature_files):
        fmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(feature_files[symbol])}
        tmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(target_files[symbol])}
        rmap={}
        for x in iter_jsonl_gz(replay_files[symbol]):
            d=str(x.get("as_of") or "")[:10]
            if d<=DEV_END and x.get("status")=="REPLAYED":rmap[d]=x
        if set(fmap)!=set(tmap):raise EvalError(f"{symbol}: feature/target observation keys differ")
        for d in sorted(fmap):
            if d>=VALIDATION_START:raise EvalError("non-Development row encountered")
            frow=fmap[d];trow=tmap[d];rrw=rmap.get(d)
            if rrw is None:raise EvalError(f"{symbol} {d}: replay provenance missing")
            profile=rrw.get("profile") or {}
            feats=flatten_base_features(frow.get("feature_values") or {})
            feats.update(build_structured(profile,gate))
            feats.pop("F071",None)
            all_feature_cols.update(feats)
            row={"symbol":symbol,"as_of":d,**feats}
            for h in HORIZONS:
                tar=(trow.get("targets") or {}).get(str(h)) or {}
                row[f"h{h}_status"]=tar.get("status")
                row[f"h{h}_direction"]=tar.get("direction_label")
                row[f"h{h}_abs_return"]=tar.get("absolute_forward_return")
                row[f"h{h}_rel_return"]=tar.get("market_relative_forward_return")
                row[f"h{h}_target_session"]=tar.get("target_session")
            rows.append(row)

    if len(rows)!=303689:raise EvalError(f"training row count changed: {len(rows)}")
    feature_cols=sorted(all_feature_cols)
    if any("F071" in c for c in feature_cols):raise EvalError("F071 leaked into training features")
    ml=require_ml()
    folds=gate.get("walk_forward_preregistration",{}).get("folds") or []
    model_families=gate.get("model_family_preregistration") or {}
    evidence=[]
    mf2_is_available=mf2_available()
    checkpoint_path=resolve(root,args.checkpoint_json)
    completed=set()
    if args.resume and checkpoint_path.exists():
        cp=load_json(checkpoint_path)
        if cp.get("version")!=VERSION:
            raise EvalError("checkpoint version mismatch")
        evidence=list(cp.get("evidence") or [])
        completed={tuple(x) for x in cp.get("completed_units") or []}
        print(f"RESUME: loaded {len(completed)} completed fold/horizon units and {len(evidence)} evidence rows",flush=True)

    def save_checkpoint():
        atomic_json(checkpoint_path,{
            "version":VERSION,
            "status":"IN_PROGRESS",
            "completed_units":[list(x) for x in sorted(completed)],
            "evidence":evidence,
            "validation_opened":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
        })

    for h in HORIZONS:
        for fold in folds:
            unit=(fold["fold_id"],h)
            if unit in completed:
                print(f"{fold['fold_id']} h{h}: SKIP COMPLETED",flush=True)
                continue
            test_start=fold["test_start"];test_end=fold["test_end"]
            print(f"{fold['fold_id']} h{h}: PREPARE",flush=True)
            direction_train=[r for r in rows if r["as_of"]<test_start and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_target_session"]<test_start and r[f"h{h}_direction"] in ("UP","DOWN")]
            direction_test=[r for r in rows if test_start<=r["as_of"]<=test_end and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")]
            return_train=[r for r in rows if r["as_of"]<test_start and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_target_session"]<test_start and r[f"h{h}_abs_return"] is not None]
            return_test=[r for r in rows if test_start<=r["as_of"]<=test_end and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_abs_return"] is not None]
            if not direction_train or not direction_test or not return_train or not return_test:
                evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"ALL","status":"INSUFFICIENT_ROWS","train_count":len(direction_train),"test_count":len(direction_test)})
                completed.add(unit);save_checkpoint();continue

            mf1=model_families["MF1_REGULARIZED_LOGISTIC_DIRECTION"]
            for rec in evaluate_mf1(direction_train,direction_test,feature_cols,f"h{h}_direction",mf1["fixed_grid"],ml,progress_prefix=f"{fold['fold_id']} h{h}"):
                evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"MF1_REGULARIZED_LOGISTIC_DIRECTION","status":"EVALUATED","train_count":len(direction_train),"test_count":len(direction_test),**rec})

            # MF2 remains fail-closed until monotonic runtime + sign map authority is certified.
            evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"MF2_MONOTONIC_GAM_DIRECTION","status":"BLOCKED_DEPENDENCY_OR_SIGN_AUTHORITY","train_count":len(direction_train),"test_count":len(direction_test),"reason":"NO_CERTIFIED_MONOTONIC_GAM_RUNTIME_AND_FIELD_LEVEL_SIGN_MAP"})

            # MF3 fail-closed: current sklearn solver cannot honor the frozen alpha x l1_ratio contract.
            mf3=model_families["MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION"]
            for rec in evaluate_mf3(return_train,return_test,feature_cols,f"h{h}_abs_return",mf3["fixed_grid"],mf3["quantiles"],ml,progress_prefix=f"{fold['fold_id']} h{h}"):
                evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","train_count":len(return_train),"test_count":len(return_test),**rec})

            completed.add(unit)
            save_checkpoint()
            print(f"{fold['fold_id']} h{h}: CHECKPOINT SAVED",flush=True)

    # Aggregate family/config evidence without opening Validation.
    mf1_configs=defaultdict(list);mf3_configs=defaultdict(list)
    for e in evidence:
        if e.get("status")!="EVALUATED":continue
        if e["family"]=="MF1_REGULARIZED_LOGISTIC_DIRECTION":
            mf1_configs[(e["horizon"],e["C"])].append(e["balanced_accuracy"])
        elif e["family"]=="MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION":
            mf3_configs[(e["horizon"],e["alpha"])].append(e["median_absolute_error"])

    selections=[]
    for h in HORIZONS:
        cand=[(sum(v)/len(v),C,len(v)) for (hh,C),v in mf1_configs.items() if hh==h]
        if cand:
            score,C,n=min(cand,key=lambda z:(-z[0],z[1]))
            selections.append({"family":"MF1_REGULARIZED_LOGISTIC_DIRECTION","horizon":h,"selected_config":{"C":C},"mean_walk_forward_balanced_accuracy":score,"fold_count":n})
        cand3=[(sum(v)/len(v),a,len(v)) for (hh,a),v in mf3_configs.items() if hh==h]
        if cand3:
            loss,a,n=min(cand3,key=lambda z:(z[0],z[1]))
            selections.append({"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","horizon":h,"selected_config":{"alpha":a},"mean_walk_forward_median_absolute_error":loss,"fold_count":n})

    report={
        "version":VERSION,"status":"READY",
        "training_gate_sha256":sha256_file(gp),"target_authority_sha256":sha256_file(tp),
        "development_only":True,
        "structured_training_matrix_materialized":True,
        "training_observation_count":len(rows),
        "training_feature_column_count":len(feature_cols),
        "training_feature_columns":feature_cols,
        "F071_in_training_features":False,
        "walk_forward_fold_count":len(folds),
        "evidence":evidence,
        "development_selected_configs":selections,
        "MF2_status":"BLOCKED_PENDING_CERTIFIED_MONOTONIC_SIGN_MAP_AND_RUNTIME",
        "MF3_status":"BLOCKED_PENDING_CERTIFIED_ELASTIC_NET_QUANTILE_LINEAR_SOLVER",
        "governance":{
            "preprocessing_fit_within_train_fold_only":True,
            "target_session_purge_enforced":True,
            "development_walk_forward_scored":True,
            "models_trained_within_development_folds":True,
            "full_development_final_model_fit":False,
            "validation_feature_matrix_opened":False,
            "validation_outcomes_opened":False,
            "final_holdout_feature_matrix_opened":False,
            "final_holdout_outcomes_opened":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_7_2_MF2_MF3_IMPLEMENTATION_AUTHORITY_BEFORE_ANY_VALIDATION_OPEN",
    }
    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    fields=sorted({k for e in evidence for k in e if not isinstance(e.get(k),(dict,list))})
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(evidence)

    print("=== M77.19.8.7 DEVELOPMENT-ONLY STRUCTURED TRAINING MATRIX & WALK-FORWARD MODEL-FAMILY EVALUATION ===")
    print("status: READY")
    print("training_observation_count:",len(rows))
    print("training_feature_column_count:",len(feature_cols))
    print("F071_in_training_features: False")
    print("walk_forward_fold_count:",len(folds))
    print("MF1_evidence_row_count:",sum(e.get("family")=="MF1_REGULARIZED_LOGISTIC_DIRECTION" and e.get("status")=="EVALUATED" for e in evidence))
    print("MF2_status: BLOCKED_PENDING_CERTIFIED_MONOTONIC_SIGN_MAP_AND_RUNTIME")
    print("MF3_status: BLOCKED_PENDING_CERTIFIED_ELASTIC_NET_QUANTILE_LINEAR_SOLVER")
    print("MF3_evidence_row_count:",sum(e.get("family")=="MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION" and e.get("status")=="EVALUATED" for e in evidence))
    print("development_selected_configs:",selections)
    print("preprocessing_fit_within_train_fold_only: True")
    print("target_session_purge_enforced: True")
    print("development_walk_forward_scored: True")
    print("full_development_final_model_fit: False")
    print("validation_outcomes_opened: False")
    print("final_holdout_outcomes_opened: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_2_MF2_MF3_IMPLEMENTATION_AUTHORITY_BEFORE_ANY_VALIDATION_OPEN")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
