#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

VERSION="M77.19.8.7.10.7.3-FROZEN-MF1-MF2-VALIDATION-SCORING-EXECUTION-WITH-DEVELOPMENT-ONLY-FIT-1.0"

MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=(5,10,20)

FROZEN_MF1={
    5:{"C":10.0},
    10:{"C":1.0},
    20:{"C":0.1},
}
FROZEN_MF2={
    5:{"l2_penalty":0.1,"spline_knots":4},
    10:{"l2_penalty":0.1,"spline_knots":4},
    20:{"l2_penalty":0.1,"spline_knots":4},
}

class ValidationExecutionError(RuntimeError):
    pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(path):
    with Path(path).open("r",encoding="utf-8") as f:
        return json.load(f)

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
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

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def load_partition(root):
    rows=[]
    files=sorted(root.glob("*.jsonl.gz"))
    if not files:
        raise ValidationExecutionError(f"no matrix files found under {root}")
    for p in files:
        rows.extend(iter_jsonl_gz(p))
    return rows,files

def normalize_nested_target_row(row,horizon,target_payload):
    out={
        "symbol":row.get("symbol"),
        "as_of":row.get("as_of"),
        "feature_source_sha256":row.get("feature_source_sha256"),
        "horizon":horizon,
    }
    if isinstance(target_payload,str):
        if target_payload in ("UP","DOWN","ZERO"):
            out["direction_label"]=target_payload
            return out
        raise ValidationExecutionError(f"unsupported nested target string for h{horizon}: {target_payload!r}")
    if not isinstance(target_payload,dict):
        raise ValidationExecutionError(f"nested target payload for h{horizon} is not dict/string: {type(target_payload).__name__}")
    direction=(
        target_payload.get("direction_label")
        or target_payload.get("direction")
        or target_payload.get("label")
        or target_payload.get(f"h{horizon}_direction")
    )
    if direction in ("UP","DOWN","ZERO"):
        out["direction_label"]=direction
    for k,v in target_payload.items():
        if k not in out:
            out[k]=v
    if out.get("direction_label") not in ("UP","DOWN","ZERO"):
        raise ValidationExecutionError(f"nested target payload for h{horizon} missing governed direction label; keys={sorted(target_payload.keys())}")
    return out

def extract_nested_targets(row):
    targets=row.get("targets")
    if not isinstance(targets,dict):
        return {}
    resolved={}
    for raw_key,payload in targets.items():
        key=str(raw_key).strip().lower()
        h=None
        if key in ("5","10","20"):
            h=int(key)
        elif key in ("h5","h10","h20"):
            h=int(key[1:])
        elif key in ("5d","10d","20d"):
            h=int(key[:-1])
        elif key.startswith("horizon_") and key.split("_",1)[1] in ("5","10","20"):
            h=int(key.split("_",1)[1])
        elif key.startswith("horizon-") and key.split("-",1)[1] in ("5","10","20"):
            h=int(key.split("-",1)[1])
        if h in HORIZONS:
            if h in resolved:
                raise ValidationExecutionError(f"duplicate nested target horizon h{h} in row {row.get('symbol')} {row.get('as_of')}")
            resolved[h]=normalize_nested_target_row(row,h,payload)
    return resolved

def load_target_root_by_horizon(root):
    root=Path(root)
    if not root.exists():
        raise ValidationExecutionError(f"target matrix root missing: {root}")
    out={5:[],10:[],20:[]}
    used={5:[],10:[],20:[]}

    explicit=False
    for h in HORIZONS:
        hp=root/f"h{h}"
        files=sorted(hp.glob("*.jsonl.gz")) if hp.exists() else []
        if files:
            explicit=True
            for p in files:
                out[h].extend(iter_jsonl_gz(p))
                used[h].append(p)
    if explicit:
        missing=[h for h in HORIZONS if not out[h]]
        if missing:
            raise ValidationExecutionError(f"target matrix explicit horizon layout incomplete under {root}: missing {missing}")
        return out,used

    files=sorted(root.rglob("*.jsonl.gz"))
    if not files:
        raise ValidationExecutionError(f"no target matrix files found under {root}")

    unresolved=[]
    ambiguous=[]
    for p in files:
        low=p.name.lower()
        hits=[h for h in HORIZONS if (f"h{h}" in low or f"horizon_{h}" in low or f"horizon-{h}" in low)]
        file_hint=hits[0] if len(hits)==1 else None
        for r in iter_jsonl_gz(p):
            nested=extract_nested_targets(r)
            if nested:
                for h,nr in sorted(nested.items()):
                    out[h].append(nr)
                    if p not in used[h]:
                        used[h].append(p)
                continue
            c=set()
            for key in ("horizon","horizon_days","holding_horizon","target_horizon","forward_horizon"):
                v=r.get(key)
                try:
                    if v is not None and int(v) in HORIZONS:
                        c.add(int(v))
                except Exception:
                    pass
            for h in HORIZONS:
                if any(k in r for k in (f"h{h}_direction",f"h{h}_return",f"h{h}_target",f"h{h}_label")):
                    c.add(h)
            if file_hint is not None:
                c.add(file_hint)
            if len(c)==1:
                h=next(iter(c))
                out[h].append(r)
                if p not in used[h]:
                    used[h].append(p)
            elif len(c)==0:
                unresolved.append((str(p),r.get("symbol"),r.get("as_of"),sorted(r.keys())))
            else:
                ambiguous.append((str(p),r.get("symbol"),r.get("as_of"),sorted(c)))

    if unresolved or ambiguous:
        raise ValidationExecutionError(
            f"target horizon resolution failed: unresolved={len(unresolved)} ambiguous={len(ambiguous)} "
            f"sample_unresolved={unresolved[:2]} sample_ambiguous={ambiguous[:2]}"
        )
    missing=[h for h in HORIZONS if not out[h]]
    if missing:
        raise ValidationExecutionError(f"target horizon resolution produced no rows for horizons {missing} under {root}")
    return out,used

def index_targets(rows,horizon):
    by_key={}
    for r in rows:
        symbol=r.get("symbol")
        as_of=str(r.get("as_of") or "")[:10]
        if not symbol or not as_of:
            continue
        label=r.get("direction_label")
        if label is None:
            label=r.get(f"h{horizon}_direction")
        if label is None:
            label=r.get("direction")
        if label is None:
            label=r.get("label")
        if label in ("UP","DOWN","ZERO"):
            by_key[(symbol,as_of)]=label
    return by_key

def extract_feature_columns(rows):
    feature_ids=set()
    for r in rows[:1000]:
        vals=r.get("feature_values")
        if isinstance(vals,dict):
            feature_ids.update(vals.keys())
    if not feature_ids:
        raise ValidationExecutionError("feature_values schema not found")
    return sorted(feature_ids)

def to_scalar(v):
    if v is None:
        return None
    if isinstance(v,bool):
        return 1.0 if v else 0.0
    if isinstance(v,(int,float)) and math.isfinite(float(v)):
        return float(v)
    if isinstance(v,str):
        s=v.strip()
        if not s:
            return None
        try:
            x=float(s)
            return x if math.isfinite(x) else None
        except Exception:
            return s
    return v

def flatten_row(r,feature_cols):
    out={"symbol":r.get("symbol"),"as_of":str(r.get("as_of") or "")[:10]}
    vals=r.get("feature_values") or {}
    for fid in feature_cols:
        out[fid]=to_scalar(vals.get(fid))
    return out

def import_module_from_path(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ValidationExecutionError(f"cannot import module from {path}")
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

def balanced_accuracy(y_true,y_pred):
    y_true=np.asarray(y_true,dtype=int)
    y_pred=np.asarray(y_pred,dtype=int)
    vals=[]
    for cls in (0,1):
        mask=(y_true==cls)
        if mask.sum()==0:
            continue
        vals.append(float((y_pred[mask]==cls).mean()))
    return float(np.mean(vals)) if vals else None

def log_loss(y,p):
    y=np.asarray(y,dtype=float)
    p=np.clip(np.asarray(p,dtype=float),1e-12,1-1e-12)
    return float(-(y*np.log(p)+(1-y)*np.log(1-p)).mean())

def brier(y,p):
    y=np.asarray(y,dtype=float)
    p=np.asarray(p,dtype=float)
    return float(np.mean((p-y)**2))

def roc_auc(y,p):
    y=np.asarray(y,dtype=int)
    p=np.asarray(p,dtype=float)
    pos=np.where(y==1)[0]
    neg=np.where(y==0)[0]
    if len(pos)==0 or len(neg)==0:
        return None
    order=np.argsort(p,kind="mergesort")
    ranks=np.empty(len(p),dtype=float)
    ranks[order]=np.arange(1,len(p)+1,dtype=float)
    # average tied ranks
    vals=defaultdict(list)
    for i,v in enumerate(p):
        vals[float(v)].append(i)
    for inds in vals.values():
        if len(inds)>1:
            avg=float(np.mean(ranks[inds]))
            ranks[inds]=avg
    u=float(ranks[pos].sum()-len(pos)*(len(pos)+1)/2.0)
    return u/(len(pos)*len(neg))

def load_training_helpers(mf1_script,mf2_script,runtime_module):
    mf1_mod=import_module_from_path("m77_19_8_7_mf1_dev",mf1_script)
    mf2_mod=import_module_from_path("m77_19_8_7_8_mf2_dev",mf2_script)
    runtime_mod=import_module_from_path("m77_19_8_7_4_runtime",runtime_module)

    FoldPreprocessor=getattr(mf2_mod,"FoldPreprocessor",None)
    if FoldPreprocessor is None:
        FoldPreprocessor=getattr(mf1_mod,"FoldPreprocessor",None)
    if FoldPreprocessor is None:
        raise ValidationExecutionError("FoldPreprocessor not found in certified Development scripts")

    evaluate_mf1=getattr(mf1_mod,"evaluate_mf1",None)
    if evaluate_mf1 is None:
        raise ValidationExecutionError("evaluate_mf1 not found in certified MF1 Development script")

    CertifiedMonotonicGAM=getattr(runtime_mod,"CertifiedMonotonicGAM",None)
    if CertifiedMonotonicGAM is None:
        raise ValidationExecutionError("CertifiedMonotonicGAM not found in certified runtime module")

    return FoldPreprocessor,evaluate_mf1,CertifiedMonotonicGAM

def load_sign_map(path):
    if not path.exists():
        raise ValidationExecutionError(f"semantic sign registry missing: {path}")
    out={}
    with path.open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            # tolerate several historical column names
            col=r.get("column") or r.get("feature_column") or r.get("encoded_column")
            sign=r.get("monotonic_sign") or r.get("sign")
            if col and sign not in (None,""):
                try:
                    out[col]=int(float(sign))
                except Exception:
                    pass
    return out

def join_rows(feature_rows,target_index,feature_cols):
    joined=[]
    zeros=0
    for r in feature_rows:
        key=(r.get("symbol"),str(r.get("as_of") or "")[:10])
        label=target_index.get(key)
        if label is None:
            continue
        if label=="ZERO":
            zeros+=1
            continue
        fr=flatten_row(r,feature_cols)
        fr["target_direction"]=label
        joined.append(fr)
    return joined,zeros

def split_dev_validation(dev_rows,val_rows,h):
    for r in dev_rows:
        r[f"h{h}_direction"]=r["target_direction"]
    for r in val_rows:
        r[f"h{h}_direction"]=r["target_direction"]
    return dev_rows,val_rows

def execute_mf1(evaluate_mf1,dev_rows,val_rows,feature_cols,h,C):
    # Exact certified callable invocation is reused. No Validation refit/retune:
    # Development-only rows are the fit partition, Validation rows score-only.
    result=evaluate_mf1(
        dev_rows,
        val_rows,
        feature_cols,
        h,
        C,
    )
    if not isinstance(result,dict):
        raise ValidationExecutionError("evaluate_mf1 returned non-dict result")
    prob=result.get("probabilities") or result.get("prob") or result.get("test_probabilities")
    pred=result.get("predictions") or result.get("pred") or result.get("test_predictions")
    if prob is None and "model" in result and "X_test" in result:
        model=result["model"]
        Xte=result["X_test"]
        prob=model.predict_proba(Xte)[:,1]
    if pred is None and prob is not None:
        pred=(np.asarray(prob)>=0.5).astype(int)
    if prob is None or pred is None:
        # Some historic evaluate_mf1 implementations return metrics only.
        # In that case we require explicit y_test plus probability-bearing fields.
        raise ValidationExecutionError("evaluate_mf1 did not expose Validation probabilities/predictions")
    y=np.asarray([1 if r["target_direction"]=="UP" else 0 for r in val_rows],dtype=int)
    prob=np.asarray(prob,dtype=float)
    pred=np.asarray(pred,dtype=int)
    if len(prob)!=len(y) or len(pred)!=len(y):
        raise ValidationExecutionError("MF1 Validation score cardinality mismatch")
    return {
        "y":y,"prob":prob,"pred":pred,
        "balanced_accuracy":balanced_accuracy(y,pred),
        "log_loss":log_loss(y,prob),
        "brier_score":brier(y,prob),
        "roc_auc":roc_auc(y,prob),
    }

def execute_mf2(FoldPreprocessor,CertifiedMonotonicGAM,dev_rows,val_rows,feature_cols,h,knots,l2,sign_map):
    prep=FoldPreprocessor().fit(dev_rows,feature_cols,sign_map)
    Xtr=prep.transform(dev_rows)
    Xva=prep.transform(val_rows)
    ytr=np.asarray([1 if r["target_direction"]=="UP" else 0 for r in dev_rows],dtype=float)
    yva=np.asarray([1 if r["target_direction"]=="UP" else 0 for r in val_rows],dtype=int)

    model=CertifiedMonotonicGAM(
        knot_count=int(knots),
        l2_penalty=float(l2),
        max_iter=300,
    ).fit(Xtr,ytr,prep.output_signs)

    prob=np.asarray(model.predict_proba(Xva)[:,1],dtype=float)
    pred=(prob>=0.5).astype(int)
    return {
        "y":yva,"prob":prob,"pred":pred,
        "balanced_accuracy":balanced_accuracy(yva,pred),
        "log_loss":log_loss(yva,prob),
        "brier_score":brier(yva,prob),
        "roc_auc":roc_auc(yva,prob),
    }

# M77.19.8.7.10.7.3.1-TARGET-MATRIX-LAYOUT-RESOLUTION-REPAIR
# M77.19.8.7.10.7.3.2-NESTED-TARGET-SCHEMA-RESOLUTION-REPAIR
# M77.19.8.7.10.7.3.2.1-MAIN-DEFINITION-RESTORATION-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--combined-invocation-json",default="reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json")
    ap.add_argument("--validation-preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill")
    ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--development-target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-runtime-module",default="src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py")
    ap.add_argument("--mf2-sign-registry-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_3_frozen_mf1_mf2_validation_scoring_execution_with_development_only_fit.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_3_validation_scoring_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()

    combined=load_json(resolve(root,args.combined_invocation_json))
    pre=load_json(resolve(root,args.validation_preregistration_json))

    if combined.get("status")!="READY":
        raise ValidationExecutionError("combined invocation authority not READY")
    if combined.get("combined_exact_invocation_authority_certified") is not True:
        raise ValidationExecutionError("combined invocation authority not certified")
    if combined.get("validation_scoring_execution_authorized") is not True:
        raise ValidationExecutionError("Validation scoring not authorized")
    if combined.get("validation_scoring_performed") is not False:
        raise ValidationExecutionError("Validation scoring unexpectedly already performed")
    if combined.get("model_family_champion_selection_authorized") is not False:
        raise ValidationExecutionError("champion selection unexpectedly authorized")
    if combined.get("final_holdout_open_authorized") is not False:
        raise ValidationExecutionError("Final Holdout unexpectedly authorized")

    if pre.get("status")!="READY" or pre.get("validation_scoring_authorized") is not True:
        raise ValidationExecutionError("Validation preregistration invalid")
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
            raise ValidationExecutionError(f"Validation governance unexpectedly relaxed: {k}")

    dev_feature_root=resolve(root,args.development_feature_root)
    val_feature_root=resolve(root,args.validation_feature_root)
    dev_target_root=resolve(root,args.development_target_root)
    val_target_root=resolve(root,args.validation_target_root)

    dev_feature_rows,dev_feature_files=load_partition(dev_feature_root)
    val_feature_rows,val_feature_files=load_partition(val_feature_root)

    feature_cols=extract_feature_columns(dev_feature_rows)
    val_cols=extract_feature_columns(val_feature_rows)
    if feature_cols!=val_cols:
        raise ValidationExecutionError("Development/Validation feature schemas differ")

    FoldPreprocessor,evaluate_mf1,CertifiedMonotonicGAM=load_training_helpers(
        resolve(root,args.mf1_development_script),
        resolve(root,args.mf2_development_script),
        resolve(root,args.mf2_runtime_module),
    )
    sign_map=load_sign_map(resolve(root,args.mf2_sign_registry_csv))

    dev_target_rows_by_h,dev_target_files_by_h=load_target_root_by_horizon(dev_target_root)
    val_target_rows_by_h,val_target_files_by_h=load_target_root_by_horizon(val_target_root)

    dev_targets_by_h={}
    val_targets_by_h={}
    for h in HORIZONS:
        dev_targets_by_h[h]=index_targets(dev_target_rows_by_h[h],h)
        val_targets_by_h[h]=index_targets(val_target_rows_by_h[h],h)
        if not dev_targets_by_h[h]:
            raise ValidationExecutionError(f"h{h}: no Development targets resolved")
        if not val_targets_by_h[h]:
            raise ValidationExecutionError(f"h{h}: no Validation targets resolved")

    evidence=[]
    family_horizon_metrics=[]

    for h in HORIZONS:
        dev_joined,dev_zero=join_rows(dev_feature_rows,dev_targets_by_h[h],feature_cols)
        val_joined,val_zero=join_rows(val_feature_rows,val_targets_by_h[h],feature_cols)
        if not dev_joined or not val_joined:
            raise ValidationExecutionError(f"h{h}: empty joined Development or Validation matrix")

        split_dev_validation(dev_joined,val_joined,h)

        mf1_cfg=FROZEN_MF1[h]
        mf1_result=execute_mf1(
            evaluate_mf1,
            dev_joined,
            val_joined,
            feature_cols,
            h,
            mf1_cfg["C"],
        )
        family_horizon_metrics.append({
            "family":MF1,
            "horizon":h,
            "config":mf1_cfg,
            "development_fit_row_count":len(dev_joined),
            "validation_score_row_count":len(val_joined),
            "development_zero_labels_excluded":dev_zero,
            "validation_zero_labels_excluded":val_zero,
            "balanced_accuracy":mf1_result["balanced_accuracy"],
            "log_loss":mf1_result["log_loss"],
            "brier_score":mf1_result["brier_score"],
            "roc_auc":mf1_result["roc_auc"],
        })

        mf2_cfg=FROZEN_MF2[h]
        mf2_result=execute_mf2(
            FoldPreprocessor,
            CertifiedMonotonicGAM,
            dev_joined,
            val_joined,
            feature_cols,
            h,
            mf2_cfg["spline_knots"],
            mf2_cfg["l2_penalty"],
            sign_map,
        )
        family_horizon_metrics.append({
            "family":MF2,
            "horizon":h,
            "config":mf2_cfg,
            "development_fit_row_count":len(dev_joined),
            "validation_score_row_count":len(val_joined),
            "development_zero_labels_excluded":dev_zero,
            "validation_zero_labels_excluded":val_zero,
            "balanced_accuracy":mf2_result["balanced_accuracy"],
            "log_loss":mf2_result["log_loss"],
            "brier_score":mf2_result["brier_score"],
            "roc_auc":mf2_result["roc_auc"],
        })

    # Stability evidence only; no champion selection.
    by_family=defaultdict(list)
    for r in family_horizon_metrics:
        by_family[r["family"]].append(r["balanced_accuracy"])

    stability={}
    for fam,vals in by_family.items():
        a=np.asarray(vals,dtype=float)
        stability[fam]={
            "mean_balanced_accuracy":float(a.mean()),
            "std_balanced_accuracy":float(a.std(ddof=0)),
            "min_balanced_accuracy":float(a.min()),
            "max_balanced_accuracy":float(a.max()),
            "positive_horizons":int((a>0.5).sum()),
            "horizon_count":len(a),
        }

    report={
        "version":VERSION,
        "status":"READY",
        "combined_invocation_authority_sha256":sha256_file(resolve(root,args.combined_invocation_json)),
        "validation_preregistration_sha256":sha256_file(resolve(root,args.validation_preregistration_json)),
        "development_feature_root":str(dev_feature_root),
        "validation_feature_root":str(val_feature_root),
        "development_target_root":str(dev_target_root),
        "validation_target_root":str(val_target_root),
        "development_target_file_count_by_horizon":{str(h):len(dev_target_files_by_h[h]) for h in HORIZONS},
        "validation_target_file_count_by_horizon":{str(h):len(val_target_files_by_h[h]) for h in HORIZONS},
        "development_target_row_count_by_horizon":{str(h):len(dev_target_rows_by_h[h]) for h in HORIZONS},
        "validation_target_row_count_by_horizon":{str(h):len(val_target_rows_by_h[h]) for h in HORIZONS},
        "target_matrix_layout_resolution":"CERTIFIED_ROOT_RECURSIVE_HORIZON_RESOLUTION_FAIL_CLOSED",
        "nested_target_schema_resolution":"TARGETS_OBJECT_H5_H10_H20_EXPLICIT_NORMALIZATION",
        "development_feature_file_count":len(dev_feature_files),
        "validation_feature_file_count":len(val_feature_files),
        "feature_column_count":len(feature_cols),
        "frozen_MF1_selected_configs":{str(k):v for k,v in FROZEN_MF1.items()},
        "frozen_MF2_selected_configs":{str(k):v for k,v in FROZEN_MF2.items()},
        "family_horizon_metrics":family_horizon_metrics,
        "validation_stability_evidence":stability,
        "validation_scoring_performed":True,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "validation_threshold_search_performed":False,
        "validation_feature_selection_search_performed":False,
        "model_family_champion_selection_authorized":False,
        "model_family_champion_selected":False,
        "final_holdout_open_authorized":False,
        "final_holdout_feature_rows_opened":False,
        "final_holdout_targets_opened":False,
        "final_holdout_outcomes_opened":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_10_7_4_VALIDATION_EVIDENCE_STABILITY_AND_FINAL_HOLDOUT_ADVANCEMENT_GATE",
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=[
            "family","horizon","config_json","development_fit_row_count",
            "validation_score_row_count","development_zero_labels_excluded",
            "validation_zero_labels_excluded","balanced_accuracy","log_loss",
            "brier_score","roc_auc"
        ]
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for r in family_horizon_metrics:
            w.writerow({
                "family":r["family"],
                "horizon":r["horizon"],
                "config_json":json.dumps(r["config"],sort_keys=True),
                "development_fit_row_count":r["development_fit_row_count"],
                "validation_score_row_count":r["validation_score_row_count"],
                "development_zero_labels_excluded":r["development_zero_labels_excluded"],
                "validation_zero_labels_excluded":r["validation_zero_labels_excluded"],
                "balanced_accuracy":r["balanced_accuracy"],
                "log_loss":r["log_loss"],
                "brier_score":r["brier_score"],
                "roc_auc":r["roc_auc"],
            })

    print("=== M77.19.8.7.10.7.3 FROZEN MF1/MF2 VALIDATION SCORING EXECUTION WITH DEVELOPMENT-ONLY FIT ===")
    print("status: READY")
    print("feature_column_count:",len(feature_cols))
    for r in family_horizon_metrics:
        print(
            f"{r['family']} h{r['horizon']}: "
            f"dev_fit={r['development_fit_row_count']} "
            f"validation={r['validation_score_row_count']} "
            f"bal_acc={r['balanced_accuracy']:.9f} "
            f"log_loss={r['log_loss']:.9f} "
            f"brier={r['brier_score']:.9f} "
            f"roc_auc={None if r['roc_auc'] is None else round(r['roc_auc'],9)}"
        )
    for fam,s in stability.items():
        print(
            f"{fam} stability: mean_bal_acc={s['mean_balanced_accuracy']:.9f} "
            f"std={s['std_balanced_accuracy']:.9f} "
            f"min={s['min_balanced_accuracy']:.9f} "
            f"positive_horizons={s['positive_horizons']}/{s['horizon_count']}"
        )
    print("validation_scoring_performed: True")
    print("validation_preprocessor_refit_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("validation_threshold_search_performed: False")
    print("validation_feature_selection_search_performed: False")
    print("model_family_champion_selection_authorized: False")
    print("model_family_champion_selected: False")
    print("final_holdout_open_authorized: False")
    print("final_holdout_feature_rows_opened: False")
    print("final_holdout_targets_opened: False")
    print("final_holdout_outcomes_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
