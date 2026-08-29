#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gc,gzip,importlib.util,json,sys,time
from pathlib import Path
import numpy as np

HORIZONS=(5,10,20)
MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
DEV_END="2017-12-31";VAL_START="2018-01-01";VAL_END="2022-12-31"
FROZEN_MF1={5:{"C":10.0},10:{"C":1.0},20:{"C":0.1}}
FROZEN_MF2={5:{"spline_knots":4,"l2_penalty":0.1},10:{"spline_knots":4,"l2_penalty":0.1},20:{"spline_knots":4,"l2_penalty":0.1}}

class WorkerError(RuntimeError):pass
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def iter_jsonl_gz(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def import_module(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:raise WorkerError(f"cannot import {path}")
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def load_sign_map(path):
    out={}
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):out[r["column_name"]]=int(r["monotonic_sign"])
    if not out:raise WorkerError("empty sign map")
    return out
def write_result(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def development_rows_for_horizon(feature_root,target_root,replay_root,gate,mf1,h):
    ff={p.name[:-9]:p for p in Path(feature_root).glob("*.jsonl.gz")}
    tf={p.name[:-9]:p for p in Path(target_root).glob("*.jsonl.gz")}
    rf={p.name[:-9]:p for p in (Path(replay_root)/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(ff)!=524 or len(tf)!=524:raise WorkerError(f"Development cardinality {len(ff)}/{len(tf)}")
    rows=[];cols=set()
    for sym in sorted(ff):
        if sym not in tf or sym not in rf:raise WorkerError(f"Development source missing {sym}")
        fm={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(ff[sym])}
        tm={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(tf[sym])}
        rm={}
        for x in iter_jsonl_gz(rf[sym]):
            d=str(x.get("as_of") or "")[:10]
            if d<=DEV_END and x.get("status")=="REPLAYED":rm[d]=x
        if set(fm)!=set(tm):raise WorkerError(f"{sym}: feature/target keys differ")
        for d in sorted(fm):
            t=(tm[d].get("targets") or {}).get(str(h)) or {}
            if t.get("status")!="MATURED" or t.get("direction_label") not in ("UP","DOWN"):
                continue
            rr=rm.get(d)
            if rr is None:raise WorkerError(f"{sym} {d}: Development replay provenance missing")
            feats=mf1.flatten_base_features(fm[d].get("feature_values") or {})
            feats.update(mf1.build_structured(rr.get("profile") or {},gate));feats.pop("F071",None);cols.update(feats)
            rows.append({"symbol":sym,"as_of":d,**feats,f"h{h}_direction":t["direction_label"]})
    return rows,sorted(cols)

def validation_target_map(target_root,h):
    out={}
    files=sorted((Path(target_root)/f"h{h}").glob("*.jsonl.gz"))
    if not files:raise WorkerError(f"Validation h{h} target directory empty")
    for p in files:
        for r in iter_jsonl_gz(p):
            if int(r.get("horizon_sessions",-1))!=h or r.get("partition")!="VALIDATION":raise WorkerError(f"{p}: target contract mismatch")
            if r.get("T_DIRECTION") not in ("UP","DOWN","ZERO"):raise WorkerError(f"{p}: bad T_DIRECTION")
            if r["T_DIRECTION"]=="ZERO":continue
            key=(r["symbol"],str(r["as_of"])[:10])
            if key in out:raise WorkerError(f"duplicate Validation target {key} h{h}")
            out[key]=r["T_DIRECTION"]
    return out

def validation_rows_for_horizon(feature_root,replay_root,gate,mf1,h,target_map,expected_cols):
    ff={p.name[:-9]:p for p in Path(feature_root).glob("*.jsonl.gz")}
    rf={p.name[:-9]:p for p in (Path(replay_root)/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(ff)!=570:raise WorkerError(f"Validation symbol count {len(ff)}")
    rows=[];seen=set()
    for sym in sorted(ff):
        if sym not in rf:raise WorkerError(f"Validation replay source missing {sym}")
        rm={}
        for x in iter_jsonl_gz(rf[sym]):
            d=str(x.get("as_of") or "")[:10]
            if VAL_START<=d<=VAL_END and x.get("status")=="REPLAYED":rm[d]=x
        for fr in iter_jsonl_gz(ff[sym]):
            d=str(fr.get("as_of") or "")[:10];lab=target_map.get((sym,d))
            if lab is None:continue
            rr=rm.get(d)
            if rr is None:raise WorkerError(f"{sym} {d}: Validation replay provenance missing")
            feats=mf1.flatten_base_features(fr.get("feature_values") or {})
            feats.update(mf1.build_structured(rr.get("profile") or {},gate));feats.pop("F071",None);seen.update(feats)
            rows.append({"symbol":sym,"as_of":d,**feats,f"h{h}_direction":lab})
    extra=seen-set(expected_cols)
    if extra:raise WorkerError(f"Validation-only columns {sorted(extra)[:10]}")
    return rows

def chunked_predict_proba(model,X,chunk_size):
    parts=[]
    for start in range(0,len(X),chunk_size):
        parts.append(model.predict_proba(X[start:start+chunk_size])[:,1])
    return np.concatenate(parts) if parts else np.empty(0,dtype=float)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True);ap.add_argument("--family",choices=[MF1,MF2],required=True);ap.add_argument("--horizon",type=int,choices=HORIZONS,required=True)
    ap.add_argument("--training-gate-json",required=True);ap.add_argument("--development-target-authority-json",required=True);ap.add_argument("--validation-target-authority-json",required=True)
    ap.add_argument("--development-feature-root",required=True);ap.add_argument("--development-target-root",required=True);ap.add_argument("--validation-feature-root",required=True);ap.add_argument("--validation-target-root",required=True);ap.add_argument("--replay-root",required=True)
    ap.add_argument("--mf1-development-script",required=True);ap.add_argument("--mf2-development-script",required=True);ap.add_argument("--mf2-runtime-module",required=True);ap.add_argument("--mf2-sign-registry-csv",required=True)
    ap.add_argument("--prediction-chunk-size",type=int,default=20000);ap.add_argument("--result-json",required=True)
    a=ap.parse_args();root=Path(a.project_root).resolve();h=a.horizon
    gate=load_json(resolve(root,a.training_gate_json));a85=load_json(resolve(root,a.development_target_authority_json));a106=load_json(resolve(root,a.validation_target_authority_json))
    mf1=import_module("m77_8736_mf1",resolve(root,a.mf1_development_script));ml=mf1.require_ml()
    print(f"UNIT {a.family} h{h}: loading Development binary rows",flush=True)
    drows,cols=development_rows_for_horizon(resolve(root,a.development_feature_root),resolve(root,a.development_target_root),resolve(root,a.replay_root),gate,mf1,h)
    de=a85["target_matrix"]["horizon_summary"][str(h)]["direction_labels"];expected_dev=int(de["UP"])+int(de["DOWN"])
    if len(drows)!=expected_dev:raise WorkerError(f"h{h}: Development binary rows {len(drows)} != {expected_dev}")
    print(f"UNIT {a.family} h{h}: Development binary rows={len(drows)} columns={len(cols)}",flush=True)

    if a.family==MF1:
        tmap=validation_target_map(resolve(root,a.validation_target_root),h)
        print(f"UNIT MF1 h{h}: loading Validation binary rows",flush=True)
        vrows=validation_rows_for_horizon(resolve(root,a.validation_feature_root),resolve(root,a.replay_root),gate,mf1,h,tmap,cols)
        s=[x for x in a106["target_horizon_summary"] if int(x["horizon"])==h][0];expected_val=int(s["UP"])+int(s["DOWN"])
        if len(vrows)!=expected_val:raise WorkerError(f"h{h}: Validation binary rows {len(vrows)} != {expected_val}")
        cfg=FROZEN_MF1[h];t=time.perf_counter()
        recs=mf1.evaluate_mf1(drows,vrows,cols,f"h{h}_direction",{"C":[cfg["C"]]},ml,progress_prefix=f"VALIDATION MF1 h{h}")
        if len(recs)!=1 or float(recs[0]["C"])!=float(cfg["C"]):raise WorkerError("MF1 evidence mismatch")
        result={"family":MF1,"horizon":h,"status":"EVALUATED","development_fit_row_count":len(drows),"validation_score_row_count":len(vrows),"elapsed_seconds":time.perf_counter()-t,**recs[0]}
        write_result(a.result_json,result);return 0

    mf2=import_module("m77_8736_mf2",resolve(root,a.mf2_development_script));rt=import_module("m77_8736_rt",resolve(root,a.mf2_runtime_module))
    FP=getattr(mf2,"FoldPreprocessor");GAM=getattr(rt,"CertifiedMonotonicGAM");sign=load_sign_map(resolve(root,a.mf2_sign_registry_csv));cfg=FROZEN_MF2[h];t=time.perf_counter()
    print(f"UNIT MF2 h{h}: fitting frozen Development preprocessor",flush=True)
    prep=FP().fit(drows,cols,sign)
    print(f"UNIT MF2 h{h}: transforming Development rows",flush=True)
    Xtr=prep.transform(drows);ytr=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in drows],dtype=float);dev_n=len(drows)
    del drows;gc.collect()
    print(f"UNIT MF2 h{h}: rows released; fitting certified GAM Xtr={Xtr.shape}",flush=True)
    model=GAM(knot_count=cfg["spline_knots"],l2_penalty=cfg["l2_penalty"],max_iter=300).fit(Xtr,ytr,prep.output_signs)
    del Xtr,ytr;gc.collect()
    print(f"UNIT MF2 h{h}: Development fit complete; loading Validation binary rows",flush=True)
    tmap=validation_target_map(resolve(root,a.validation_target_root),h)
    vrows=validation_rows_for_horizon(resolve(root,a.validation_feature_root),resolve(root,a.replay_root),gate,mf1,h,tmap,cols)
    s=[x for x in a106["target_horizon_summary"] if int(x["horizon"])==h][0];expected_val=int(s["UP"])+int(s["DOWN"])
    if len(vrows)!=expected_val:raise WorkerError(f"h{h}: Validation binary rows {len(vrows)} != {expected_val}")
    print(f"UNIT MF2 h{h}: transforming Validation rows={len(vrows)}",flush=True)
    Xv=prep.transform(vrows);yv=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in vrows],dtype=int);val_n=len(vrows)
    del vrows;gc.collect()
    print(f"UNIT MF2 h{h}: chunked certified predict_proba chunk_size={a.prediction_chunk_size}",flush=True)
    prob=chunked_predict_proba(model,Xv,a.prediction_chunk_size);del Xv;gc.collect();pred=(prob>=0.5).astype(int)
    bal=float(ml["balanced_accuracy_score"](yv,pred));ll=float(ml["log_loss"](yv,prob,labels=[0,1]));br=float(ml["brier_score_loss"](yv,prob))
    try:auc=float(ml["roc_auc_score"](yv,prob))
    except Exception:auc=None
    result={"family":MF2,"horizon":h,"status":"EVALUATED","development_fit_row_count":dev_n,"validation_score_row_count":val_n,"spline_knots":cfg["spline_knots"],"l2_penalty":cfg["l2_penalty"],"balanced_accuracy":bal,"log_loss":ll,"brier_score":br,"roc_auc":auc,"elapsed_seconds":time.perf_counter()-t,"prediction_execution_mode":"CHUNKED_EXACT_CERTIFIED_PREDICT_PROBA","prediction_chunk_size":a.prediction_chunk_size}
    write_result(a.result_json,result);return 0
if __name__=="__main__":raise SystemExit(main())
