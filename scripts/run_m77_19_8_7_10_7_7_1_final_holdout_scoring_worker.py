#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,importlib.util,json,math,sys,gc
from pathlib import Path
import numpy as np

class WorkerError(RuntimeError):pass
def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def rows_gz(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def imp(name,path):
    s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def sign_map(path):
    out={}
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):out[r["column_name"]]=int(r["monotonic_sign"])
    return out
def holdout_rows(feature_root,target_root,replay_root,gate,mf2,h):
    ff={p.name[:-9]:p for p in Path(feature_root).glob("*.jsonl.gz")}
    tf={p.name[:-9]:p for p in (Path(target_root)/f"h{h}").glob("*.jsonl.gz")}
    rf={p.name[:-9]:p for p in (Path(replay_root)/"weekly"/"profiles").glob("*.jsonl.gz")}
    if not ff or not tf:raise WorkerError("Final Holdout feature/target files missing")
    rows=[];cols=set()
    for sym in sorted(tf):
        if sym not in ff or sym not in rf:raise WorkerError(f"{sym}: feature/replay missing")
        fmap={str(x["as_of"])[:10]:x for x in rows_gz(ff[sym])}
        tmap={str(x["as_of"])[:10]:x for x in rows_gz(tf[sym])}
        need=set(tmap)
        rmap={}
        for x in rows_gz(rf[sym]):
            d=str(x.get("as_of") or "")[:10]
            if d in need and x.get("status")=="REPLAYED":rmap[d]=x
        for d in sorted(tmap):
            frow=fmap.get(d);rr=rmap.get(d);t=tmap[d]
            if frow is None or rr is None:raise WorkerError(f"{sym} {d}: PIT join missing")
            lab=t.get("T_DIRECTION")
            if lab=="ZERO":
                continue
            if lab not in ("UP","DOWN"):
                raise WorkerError(f"{sym} {d}: noncanonical holdout label {lab}")
            feats=mf2.flatten_base_features(frow.get("feature_values") or {})
            feats.update(mf2.build_structured(rr.get("profile") or {},gate))
            feats.pop("F071",None);cols.update(feats)
            rows.append({"symbol":sym,"as_of":d,**feats,f"h{h}_direction":lab})
    return rows,sorted(cols)
def metric_bundle(y,prob):
    from sklearn.metrics import balanced_accuracy_score,log_loss,brier_score_loss,roc_auc_score
    y=np.asarray(y,dtype=int);prob=np.asarray(prob,dtype=float);pred=(prob>=0.5).astype(int)
    out={"balanced_accuracy":float(balanced_accuracy_score(y,pred)),
         "log_loss":float(log_loss(y,prob,labels=[0,1])),
         "brier_score":float(brier_score_loss(y,prob))}
    try:out["roc_auc"]=float(roc_auc_score(y,prob))
    except Exception:out["roc_auc"]=None
    return out
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True);ap.add_argument("--family",required=True);ap.add_argument("--horizon",type=int,required=True)
    ap.add_argument("--authority-json",required=True);ap.add_argument("--development-feature-root",required=True);ap.add_argument("--development-target-root",required=True)
    ap.add_argument("--final-holdout-feature-root",required=True);ap.add_argument("--final-holdout-target-root",required=True);ap.add_argument("--replay-root",required=True)
    ap.add_argument("--training-gate-json",required=True);ap.add_argument("--mf1-development-script",required=True);ap.add_argument("--mf2-development-script",required=True)
    ap.add_argument("--mf2-runtime-module",required=True);ap.add_argument("--mf2-sign-registry-csv",required=True)
    ap.add_argument("--prediction-chunk-size",type=int,default=20000);ap.add_argument("--output-json",required=True)
    a=ap.parse_args();root=Path(a.project_root).resolve();h=a.horizon
    auth=J(R(root,a.authority_json));gate=J(R(root,a.training_gate_json))
    if auth.get("status")!="READY" or auth.get("final_holdout_scoring_execution_authorized") is not True:raise WorkerError("10.7.7 authority invalid")
    expected=int((auth.get("final_holdout_binary_eligible_rows") or {}).get(str(h),-1))
    mf1=imp("m77_mf1_exact",R(root,a.mf1_development_script));mf2=imp("m77_mf2_exact",R(root,a.mf2_development_script))
    dev_rows,feature_cols=mf2.load_rows(R(root,a.development_feature_root),R(root,a.development_target_root),R(root,a.replay_root),gate)
    dtr=[r for r in dev_rows if r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")]
    dev_count=len(dtr)
    print(f"UNIT {a.family} h{h}: Development binary rows={dev_count} columns={len(feature_cols)}",flush=True)
    test_rows,test_cols=holdout_rows(R(root,a.final_holdout_feature_root),R(root,a.final_holdout_target_root),R(root,a.replay_root),gate,mf2,h)
    if len(test_rows)!=expected:raise WorkerError(f"Final Holdout binary population changed {len(test_rows)}!={expected}")
    if set(test_cols)-set(feature_cols):raise WorkerError(f"Final Holdout introduced unknown model columns: {sorted(set(test_cols)-set(feature_cols))[:10]}")
    y=[1 if r[f"h{h}_direction"]=="UP" else 0 for r in test_rows]
    fam=a.family
    if fam=="MF1_REGULARIZED_LOGISTIC_DIRECTION":
        cfg=auth["frozen_MF1_selected_configs"][str(h)]
        ml=mf1.require_ml()
        rec=mf1.evaluate_mf1(dtr,test_rows,feature_cols,f"h{h}_direction",{"C":[float(cfg["C"])]},ml,progress_prefix=f"FINAL_HOLDOUT MF1 h{h}")[0]
        metrics={k:rec.get(k) for k in ("balanced_accuracy","log_loss","brier_score","roc_auc")}
        config={"C":float(cfg["C"])}
    elif fam=="MF2_MONOTONIC_GAM_DIRECTION":
        cfg=auth["frozen_MF2_selected_configs"][str(h)]
        runtime=imp("m77_mf2_runtime_exact",R(root,a.mf2_runtime_module))
        sm=sign_map(R(root,a.mf2_sign_registry_csv))
        print(f"UNIT MF2 h{h}: fitting frozen Development preprocessor",flush=True)
        prep=mf2.FoldPreprocessor().fit(dtr,feature_cols,sm)
        print(f"UNIT MF2 h{h}: transforming Development",flush=True)
        Xtr=prep.transform(dtr);ytr=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in dtr],dtype=float)
        del dev_rows,dtr;gc.collect()
        print(f"UNIT MF2 h{h}: fitting certified GAM Xtr={Xtr.shape}",flush=True)
        model=runtime.CertifiedMonotonicGAM(knot_count=int(cfg["spline_knots"]),l2_penalty=float(cfg["l2_penalty"]),max_iter=300).fit(Xtr,ytr,prep.output_signs)
        del Xtr,ytr;gc.collect()
        probs=[]
        n=max(1,a.prediction_chunk_size)
        print(f"UNIT MF2 h{h}: chunked transform/predict chunk_size={n}",flush=True)
        for i in range(0,len(test_rows),n):
            X=prep.transform(test_rows[i:i+n]);probs.append(model.predict_proba(X)[:,1]);del X;gc.collect()
        prob=np.concatenate(probs) if probs else np.empty(0)
        metrics=metric_bundle(y,prob)
        config={"spline_knots":int(cfg["spline_knots"]),"l2_penalty":float(cfg["l2_penalty"])}
    else:raise WorkerError(f"unsupported family {fam}")
    out={"status":"READY","family":fam,"horizon":h,"config":config,"development_binary_rows":dev_count,
         "final_holdout_binary_rows":len(test_rows),"decision_threshold":0.5,"metrics":metrics,
         "development_only_fit":True,"validation_rows_used_for_fit":False,"final_holdout_rows_used_for_fit":False,
         "threshold_search_performed":False,"feature_selection_search_performed":False,"hyperparameter_search_performed":False,
         "model_family_champion_selected":False,"production_authority_effect":False}
    R(root,a.output_json).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"UNIT {fam} h{h}: READY bal_acc={metrics['balanced_accuracy']:.9f}",flush=True)
if __name__=="__main__":main()
