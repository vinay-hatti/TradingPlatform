#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,tempfile,time
from pathlib import Path
import numpy as np

VERSION="M77.19.8.7.6.4-SINGLE-REAL-WF1-H5-Q050-CANARY-FULL-DEVELOPMENT-REAUTHORIZATION-GATE-1.0"
EXPECTED_8763_VERSION="M77.19.8.7.6.3-MF3-DIRECT-CONVEX-OPTIMIZATION-LARGE-MATRIX-CANARY-CERTIFICATION-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"
EXPECTED_85_VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"

DEV_END="2017-12-31"
CANARY_FOLD="WF1"
CANARY_HORIZON=5
CANARY_QUANTILE=0.50
CANARY_ALPHA=0.001
CANARY_L1_RATIO=0.50
MAX_CANARY_SECONDS=300.0
MIN_OBJECTIVE_IMPROVEMENT_VS_ZERO=-1e-12

class CanaryError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def get_path(obj,path):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def scalar(v):
    if v is None:return None
    if isinstance(v,(bool,int,float,str)):return v
    return None

def flatten_base_features(values):
    out={}
    for fid,v in sorted((values or {}).items()):
        if fid=="F071":continue
        if isinstance(v,dict):
            if fid!="F070":continue
            for k,x in sorted(v.items()):
                if isinstance(x,(bool,int,float,str)) or x is None: out[f"{fid}__{k}"]=x
        elif isinstance(v,(bool,int,float,str)) or v is None:
            out[fid]=v
    return out

def build_structured(profile,gate):
    out={}
    for rec in gate.get("structured_columns") or []:
        fid=rec["feature_id"];source=rec["source_path"];col=rec["column_name"]
        payload=profile.get("timeframe_states") if fid=="F012" else profile.get("institutional_volume")
        out[col]=scalar(get_path(payload or {},source))
    return out

class FoldPreprocessor:
    def fit(self,rows,feature_cols):
        self.feature_cols=list(feature_cols)
        self.numeric=[];self.categorical=[]
        self.medians={};self.means={};self.stds={};self.categories={}
        for c in self.feature_cols:
            vals=[r.get(c) for r in rows if r.get(c) is not None]
            is_num=bool(vals) and all(isinstance(v,(bool,int,float,np.integer,np.floating)) and not isinstance(v,str) for v in vals)
            if is_num:
                self.numeric.append(c)
                arr=np.asarray([float(r.get(c)) for r in rows if r.get(c) is not None],dtype=float)
                med=float(np.median(arr));mean=float(np.mean(arr));std=float(np.std(arr))
                if not math.isfinite(std) or std<1e-12:std=1.0
                self.medians[c]=med;self.means[c]=mean;self.stds[c]=std
            else:
                self.categorical.append(c)
                cats=sorted({str(r.get(c)) if r.get(c) is not None else "__MISSING__" for r in rows})
                if "__UNKNOWN__" not in cats:cats.append("__UNKNOWN__")
                self.categories[c]=cats
        return self

    def transform(self,rows):
        n=len(rows);blocks=[]
        for c in self.numeric:
            v=np.empty(n,dtype=float);m=np.zeros(n,dtype=float)
            med=self.medians[c];mean=self.means[c];std=self.stds[c]
            for i,r in enumerate(rows):
                x=r.get(c)
                if x is None or not isinstance(x,(bool,int,float,np.integer,np.floating)) or not math.isfinite(float(x)):
                    v[i]=med;m[i]=1.0
                else:v[i]=float(x)
            blocks.extend([((v-mean)/std)[:,None],m[:,None]])
        for c in self.categorical:
            cats=self.categories[c];idx={x:i for i,x in enumerate(cats)};unk=idx["__UNKNOWN__"]
            b=np.zeros((n,len(cats)),dtype=float)
            for i,r in enumerate(rows):
                val="__MISSING__" if r.get(c) is None else str(r.get(c))
                b[i,idx.get(val,unk)]=1.0
            blocks.append(b)
        return np.column_stack(blocks) if blocks else np.empty((n,0),dtype=float)

def pinball(y,p,q):
    r=np.asarray(y)-np.asarray(p)
    return float(np.where(r>=0,q*r,(q-1)*r).mean())

def load_canary_rows(feature_root,target_root,replay_root,gate,fold):
    ts=fold["test_start"];te=fold["test_end"]
    feature_files={p.name[:-9]:p for p in feature_root.glob("*.jsonl.gz")}
    target_files={p.name[:-9]:p for p in target_root.glob("*.jsonl.gz")}
    replay_files={p.name[:-9]:p for p in (replay_root/"weekly"/"profiles").glob("*.jsonl.gz")}
    train=[];test=[];feature_cols=set()
    for symbol in sorted(feature_files):
        fmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(feature_files[symbol])}
        tmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(target_files[symbol])}
        rmap={}
        for x in iter_jsonl_gz(replay_files[symbol]):
            d=str(x.get("as_of") or "")[:10]
            if d<=DEV_END and x.get("status")=="REPLAYED":rmap[d]=x
        for d in sorted(fmap):
            t=(tmap[d].get("targets") or {}).get(str(CANARY_HORIZON)) or {}
            if t.get("status")!="MATURED" or t.get("absolute_forward_return") is None: continue
            if d<ts and not (t.get("target_session") and t["target_session"]<ts): continue
            if d>te: continue
            rr=rmap.get(d)
            if rr is None: continue
            feats=flatten_base_features(fmap[d].get("feature_values") or {})
            feats.update(build_structured(rr.get("profile") or {},gate))
            feats.pop("F071",None)
            feature_cols.update(feats)
            row={"symbol":symbol,"as_of":d,**feats,"target":float(t["absolute_forward_return"])}
            if d<ts: train.append(row)
            elif ts<=d<=te:test.append(row)
    return train,test,sorted(feature_cols)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--direct-solver-certification-json",default="reports/m77_19_8_7_6_3_mf3_direct_convex_optimization_large_matrix_canary_certification.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--feature-matrix-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_6_4_single_real_wf1_h5_q050_canary_full_development_reauthorization_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_6_4_real_canary_telemetry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cp=resolve(root,a.direct_solver_certification_json);gp=resolve(root,a.training_gate_json);tp=resolve(root,a.target_authority_json)
    cert=load_json(cp);gate=load_json(gp);ta=load_json(tp)
    if cert.get("version")!=EXPECTED_8763_VERSION or cert.get("status")!="READY":raise CanaryError("M77.19.8.7.6.3 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise CanaryError("M77.19.8.6 gate invalid")
    if ta.get("version")!=EXPECTED_85_VERSION or ta.get("status")!="READY":raise CanaryError("M77.19.8.5 authority invalid")
    if not cert.get("real_development_canary_authorized"):raise CanaryError("real canary not authorized")
    if cert.get("validation_open_authorized") is not False or cert.get("final_holdout_open_authorized") is not False:raise CanaryError("sealed partition governance violated")

    folds=gate.get("walk_forward_preregistration",{}).get("folds") or []
    fold=next((x for x in folds if x.get("fold_id")==CANARY_FOLD),None)
    if not fold:raise CanaryError("WF1 not found in frozen gate")

    print("Loading single real Development canary matrix...",flush=True)
    train,test,feature_cols=load_canary_rows(resolve(root,a.feature_matrix_root),resolve(root,a.target_root),resolve(root,a.replay_root),gate,fold)
    if not train or not test:raise CanaryError("canary train/test empty")
    prep=FoldPreprocessor().fit(train,feature_cols)
    Xtr=prep.transform(train);Xte=prep.transform(test)
    ytr=np.asarray([r["target"] for r in train],dtype=float)
    yte=np.asarray([r["target"] for r in test],dtype=float)

    from trading_ai.research.m77.m77_19_8_7_6_3_direct_mf3 import DirectProximalSubgradientQuantile,exact_objective

    telemetry=[]
    def progress(info):
        telemetry.append(dict(info))
        print(f"CANARY iter={info['iteration']} objective={info['exact_objective']:.10f} step={info['step_size']:.6g} delta={info['delta']:.6g} elapsed={info['elapsed_seconds']:.2f}s",flush=True)

    print(f"CANARY WF1 h5 q=0.50 alpha={CANARY_ALPHA} l1={CANARY_L1_RATIO} train={len(train)} test={len(test)} features={Xtr.shape[1]} START",flush=True)
    t0=time.perf_counter()
    model=DirectProximalSubgradientQuantile(
        CANARY_QUANTILE,CANARY_ALPHA,CANARY_L1_RATIO,
        max_iter=3000,tol=2e-6,initial_step=.30,progress_every=100
    ).fit(Xtr,ytr,progress_callback=progress)
    elapsed=time.perf_counter()-t0
    pred=model.predict(Xte)
    test_pinball=pinball(yte,pred,CANARY_QUANTILE)
    zero_pred=np.full_like(yte,float(np.quantile(ytr,CANARY_QUANTILE)))
    zero_pinball=pinball(yte,zero_pred,CANARY_QUANTILE)
    directional_accuracy=float(np.mean((yte>0)==(pred>0)))
    median_abs_error=float(np.median(np.abs(yte-pred)))
    objective_improvement=zero_pinball-test_pinball

    runtime_pass=elapsed<=MAX_CANARY_SECONDS
    numerical_pass=bool(np.isfinite(pred).all() and np.isfinite(model.objective_))
    economic_sanity_pass=objective_improvement>=MIN_OBJECTIVE_IMPROVEMENT_VS_ZERO
    full_auth=bool(runtime_pass and numerical_pass and economic_sanity_pass)

    if not runtime_pass:
        decision="BLOCK_FULL_DEVELOPMENT_RUNTIME"
    elif not numerical_pass:
        decision="BLOCK_FULL_DEVELOPMENT_NUMERICAL"
    elif not economic_sanity_pass:
        decision="BLOCK_FULL_DEVELOPMENT_CANARY_OBJECTIVE"
    else:
        decision="AUTHORIZE_FULL_MF3_DEVELOPMENT_WALK_FORWARD"

    report={
        "version":VERSION,"status":"READY",
        "direct_solver_certification_sha256":sha256_file(cp),"training_gate_sha256":sha256_file(gp),"target_authority_sha256":sha256_file(tp),
        "canary_scope":{"fold":"WF1","horizon":5,"quantile":0.5,"alpha":CANARY_ALPHA,"l1_ratio":CANARY_L1_RATIO},
        "train_count":len(train),"test_count":len(test),"expanded_feature_count":int(Xtr.shape[1]),
        "elapsed_seconds":elapsed,"iterations":model.n_iter_,"converged":model.converged_,
        "train_exact_objective":model.objective_,"test_pinball_loss":test_pinball,
        "zero_model_test_pinball_loss":zero_pinball,"test_pinball_improvement_vs_zero":objective_improvement,
        "directional_accuracy_from_median_sign":directional_accuracy,"median_absolute_error":median_abs_error,
        "runtime_limit_seconds":MAX_CANARY_SECONDS,"runtime_pass":runtime_pass,
        "numerical_pass":numerical_pass,"economic_sanity_pass":economic_sanity_pass,
        "decision":decision,"full_development_walk_forward_authorized":full_auth,
        "validation_open_authorized":False,"final_holdout_open_authorized":False,
        "MF1_retuning_authorized":False,"production_authority_effect":False,
        "next_step":"PATCH_M77_19_8_7_6_TO_DIRECT_MF3_AND_RESUME_FULL_DEVELOPMENT" if full_auth else "REVIEW_M77_19_8_7_6_4_CANARY_FAILURE_BEFORE_ANY_FURTHER_MF3_EXECUTION",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["iteration","exact_objective","step_size","delta","elapsed_seconds"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(telemetry)

    print("=== M77.19.8.7.6.4 SINGLE REAL WF1/H5/Q0.50 CANARY & FULL-DEVELOPMENT REAUTHORIZATION GATE ===")
    print("status: READY")
    print("train_count:",len(train))
    print("test_count:",len(test))
    print("expanded_feature_count:",Xtr.shape[1])
    print("elapsed_seconds:",elapsed)
    print("iterations:",model.n_iter_)
    print("converged:",model.converged_)
    print("train_exact_objective:",model.objective_)
    print("test_pinball_loss:",test_pinball)
    print("zero_model_test_pinball_loss:",zero_pinball)
    print("test_pinball_improvement_vs_zero:",objective_improvement)
    print("directional_accuracy_from_median_sign:",directional_accuracy)
    print("median_absolute_error:",median_abs_error)
    print("runtime_pass:",runtime_pass)
    print("numerical_pass:",numerical_pass)
    print("economic_sanity_pass:",economic_sanity_pass)
    print("decision:",decision)
    print("full_development_walk_forward_authorized:",full_auth)
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("MF1_retuning_authorized: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
