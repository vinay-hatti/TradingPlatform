#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,tempfile,time
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

VERSION="M77.19.8.7.6-DEVELOPMENT-ONLY-MF2-MF3-WALK-FORWARD-EVALUATION-WITH-CHECKPOINTS-1.0"
EXPECTED_875_VERSION="M77.19.8.7.5-MF2-EXECUTION-PREFLIGHT-MF3-SCALABLE-SOLVER-PARITY-AUTHORITY-1.0"
EXPECTED_873_VERSION="M77.19.8.7.3-MF2-MONOTONIC-SIGN-SEMANTIC-AUTHORITY-MF3-SOLVER-DECISION-GATE-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"
EXPECTED_85_VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
HORIZONS=[5,10,20]

class EvaluationError(RuntimeError):pass

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise EvaluationError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

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
                if isinstance(x,(bool,int,float,str)) or x is None:out[f"{fid}__{k}"]=x
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
    """Deterministic train-fold-only preprocessor with stable numeric/categorical expansion."""
    def fit(self,rows,feature_cols,sign_map):
        self.feature_cols=list(feature_cols)
        self.numeric=[];self.categorical=[]
        self.medians={};self.means={};self.stds={};self.categories={}
        self.output_names=[];self.output_signs=[]
        for c in self.feature_cols:
            vals=[r.get(c) for r in rows if r.get(c) is not None]
            is_num=bool(vals) and all(isinstance(v,(bool,int,float,np.integer,np.floating)) and not isinstance(v,str) for v in vals)
            if is_num:
                self.numeric.append(c)
                arr=np.asarray([float(r.get(c)) for r in rows if r.get(c) is not None],dtype=float)
                med=float(np.median(arr));mean=float(np.mean(arr));std=float(np.std(arr))
                if not math.isfinite(std) or std<1e-12:std=1.0
                self.medians[c]=med;self.means[c]=mean;self.stds[c]=std
                self.output_names.extend([c,c+"__MISSING"])
                self.output_signs.extend([int(sign_map.get(c,0)),0])
            else:
                self.categorical.append(c)
                cats=sorted({str(r.get(c)) if r.get(c) is not None else "__MISSING__" for r in rows})
                if "__UNKNOWN__" not in cats:cats.append("__UNKNOWN__")
                self.categories[c]=cats
                for cat in cats:
                    self.output_names.append(f"{c}=={cat}")
                    self.output_signs.append(0)
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

def balanced_accuracy(y,p):
    y=np.asarray(y,dtype=int);p=np.asarray(p,dtype=int)
    vals=[]
    for cls in (0,1):
        mask=y==cls
        if mask.any():vals.append(float((p[mask]==cls).mean()))
    return float(np.mean(vals)) if vals else None

def pinball(y,p,q):
    r=np.asarray(y)-np.asarray(p)
    return float(np.where(r>=0,q*r,(q-1)*r).mean())

def load_rows(feature_root,target_root,replay_root,gate):
    feature_files={p.name[:-9]:p for p in feature_root.glob("*.jsonl.gz")}
    target_files={p.name[:-9]:p for p in target_root.glob("*.jsonl.gz")}
    replay_files={p.name[:-9]:p for p in (replay_root/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(feature_files)!=524 or len(target_files)!=524:raise EvaluationError("expected 524 Development feature/target files")
    rows=[];feature_cols=set()
    for symbol in sorted(feature_files):
        fmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(feature_files[symbol])}
        tmap={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(target_files[symbol])}
        rmap={}
        for x in iter_jsonl_gz(replay_files[symbol]):
            d=str(x.get("as_of") or "")[:10]
            if d<=DEV_END and x.get("status")=="REPLAYED":rmap[d]=x
        if set(fmap)!=set(tmap):raise EvaluationError(f"{symbol}: feature/target keys differ")
        for d in sorted(fmap):
            if d>=VALIDATION_START:raise EvaluationError("non-Development row encountered")
            rr=rmap.get(d)
            if rr is None:raise EvaluationError(f"{symbol} {d}: replay row missing")
            feats=flatten_base_features(fmap[d].get("feature_values") or {})
            feats.update(build_structured(rr.get("profile") or {},gate))
            feats.pop("F071",None)
            feature_cols.update(feats)
            row={"symbol":symbol,"as_of":d,**feats}
            for h in HORIZONS:
                t=(tmap[d].get("targets") or {}).get(str(h)) or {}
                row[f"h{h}_status"]=t.get("status");row[f"h{h}_direction"]=t.get("direction_label")
                row[f"h{h}_abs_return"]=t.get("absolute_forward_return");row[f"h{h}_target_session"]=t.get("target_session")
            rows.append(row)
    if len(rows)!=303689:raise EvaluationError(f"Development row count changed: {len(rows)}")
    return rows,sorted(feature_cols)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--execution-authority-json",default="reports/m77_19_8_7_5_mf2_execution_preflight_mf3_scalable_solver_parity_authority.json")
    ap.add_argument("--semantic-authority-json",default="reports/m77_19_8_7_3_mf2_monotonic_sign_semantic_authority_mf3_solver_decision_gate.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--feature-matrix-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_6_walk_forward_checkpoint.json")
    ap.add_argument("--resume",action="store_true")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_6_development_only_mf2_mf3_walk_forward_evaluation_with_checkpoints.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_6_mf2_mf3_walk_forward_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    xp=resolve(root,a.execution_authority_json);sp=resolve(root,a.semantic_authority_json);gp=resolve(root,a.training_gate_json);tp=resolve(root,a.target_authority_json)
    ex=load_json(xp);sem=load_json(sp);gate=load_json(gp);ta=load_json(tp)
    if ex.get("version")!=EXPECTED_875_VERSION or ex.get("status")!="READY":raise EvaluationError("M77.19.8.7.5 authority invalid")
    if sem.get("version")!=EXPECTED_873_VERSION or sem.get("status")!="READY":raise EvaluationError("M77.19.8.7.3 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise EvaluationError("M77.19.8.6 gate invalid")
    if ta.get("version")!=EXPECTED_85_VERSION or ta.get("status")!="READY":raise EvaluationError("M77.19.8.5 authority invalid")
    if not ex.get("MF2",{}).get("development_walk_forward_execution_authorized"):raise EvaluationError("MF2 execution not authorized")
    if not ex.get("MF3",{}).get("development_walk_forward_execution_authorized"):raise EvaluationError("MF3 execution not authorized")
    if ex.get("validation_open_authorized") is not False or ex.get("final_holdout_open_authorized") is not False:raise EvaluationError("sealed partition governance violated")

    from trading_ai.research.m77.m77_19_8_7_4_certified_solvers import CertifiedMonotonicGAM
    from trading_ai.research.m77.m77_19_8_7_6_1_scalable_mf3 import CompiledADMMElasticNetQuantile

    sign_csv=root/"reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv"
    sign_map={}
    with sign_csv.open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):sign_map[r["column_name"]]=int(r["monotonic_sign"])

    print("Loading frozen Development matrix...",flush=True)
    rows,feature_cols=load_rows(resolve(root,a.feature_matrix_root),resolve(root,a.target_root),resolve(root,a.replay_root),gate)
    print(f"Development rows={len(rows)} raw_feature_columns={len(feature_cols)}",flush=True)

    folds=gate.get("walk_forward_preregistration",{}).get("folds") or []
    fam=gate.get("model_family_preregistration") or {}
    mf2_grid=fam["MF2_MONOTONIC_GAM_DIRECTION"]["fixed_grid"]
    mf3_grid=fam["MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION"]["fixed_grid"]
    mf3_q=fam["MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION"]["quantiles"]

    checkpoint=resolve(root,a.checkpoint_json);evidence=[];done=set();config_done=set()
    if a.resume and checkpoint.exists():
        cp=load_json(checkpoint)
        if cp.get("version")!=VERSION:raise EvaluationError("checkpoint version mismatch")
        evidence=list(cp.get("evidence") or []);done={tuple(x) for x in cp.get("completed_units") or []};config_done={tuple(x) for x in cp.get("completed_configs") or []}
        print(f"RESUME loaded completed_units={len(done)} evidence_rows={len(evidence)}",flush=True)

    def save():
        atomic_json(checkpoint,{
            "version":VERSION,"status":"IN_PROGRESS","completed_units":[list(x) for x in sorted(done)],"completed_configs":[list(x) for x in sorted(config_done)],
            "evidence":evidence,"validation_opened":False,"final_holdout_opened":False,"production_authority_effect":False
        })

    # One fold+horizon checkpoint unit. Preprocessing is fit once and reused across all configs.
    for h in HORIZONS:
        for fold in folds:
            unit=(fold["fold_id"],h)
            if unit in done:
                print(f"{fold['fold_id']} h{h}: SKIP COMPLETED",flush=True);continue
            ts=fold["test_start"];te=fold["test_end"]
            dtr=[r for r in rows if r["as_of"]<ts and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_target_session"]<ts and r[f"h{h}_direction"] in ("UP","DOWN")]
            dte=[r for r in rows if ts<=r["as_of"]<=te and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")]
            rte=[r for r in rows if ts<=r["as_of"]<=te and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_abs_return"] is not None]
            rtr=[r for r in rows if r["as_of"]<ts and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_target_session"]<ts and r[f"h{h}_abs_return"] is not None]
            print(f"{fold['fold_id']} h{h}: train={len(dtr)} test={len(dte)} PREPROCESS",flush=True)
            prep=FoldPreprocessor().fit(dtr,feature_cols,sign_map)
            Xdtr=prep.transform(dtr);Xdte=prep.transform(dte)
            Xrtr=prep.transform(rtr);Xrte=prep.transform(rte)
            ydtr=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in dtr],dtype=float)
            ydte=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in dte],dtype=int)
            yrtr=np.asarray([float(r[f"h{h}_abs_return"]) for r in rtr],dtype=float)
            yrte=np.asarray([float(r[f"h{h}_abs_return"]) for r in rte],dtype=float)

            # MF2 fixed grid.
            for knots in mf2_grid["spline_knots"]:
                for l2 in mf2_grid["l2_penalty"]:
                    cfg=("MF2",fold["fold_id"],h,str(knots),str(l2))
                    if cfg in config_done:
                        print(f"{fold['fold_id']} h{h} MF2 knots={knots} l2={l2} SKIP COMPLETED",flush=True);continue
                    t=time.perf_counter()
                    print(f"{fold['fold_id']} h{h} MF2 knots={knots} l2={l2} START",flush=True)
                    m=CertifiedMonotonicGAM(knot_count=int(knots),l2_penalty=float(l2),max_iter=300).fit(Xdtr,ydtr,prep.output_signs)
                    prob=m.predict_proba(Xdte)[:,1];pred=(prob>=.5).astype(int)
                    bal=balanced_accuracy(ydte,pred)
                    evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"MF2_MONOTONIC_GAM_DIRECTION","status":"EVALUATED","spline_knots":knots,"l2_penalty":l2,"train_count":len(dtr),"test_count":len(dte),"balanced_accuracy":bal,"elapsed_seconds":time.perf_counter()-t})
                    config_done.add(cfg);save()
                    print(f"{fold['fold_id']} h{h} MF2 knots={knots} l2={l2} DONE bal_acc={bal:.6f} CHECKPOINT",flush=True)

            # MF3 fixed grid; quantile family metrics summarized per alpha/l1 config.
            for alpha in mf3_grid["alpha"]:
                for l1r in mf3_grid["l1_ratio"]:
                    cfg=("MF3",fold["fold_id"],h,str(alpha),str(l1r))
                    if cfg in config_done:
                        print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} SKIP COMPLETED",flush=True);continue
                    qloss=[];median_pred=None;t=time.perf_counter();qtelemetry=[]
                    print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} START",flush=True)
                    for q in mf3_q:
                        print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} q={q} START",flush=True)
                        def progress(info,_q=q):
                            print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} q={_q} iter={info['iteration']} primal={info['primal_residual_norm']:.6g} dual={info['dual_residual_norm']:.6g} elapsed={info['elapsed_seconds']:.1f}s",flush=True)
                        qm=CompiledADMMElasticNetQuantile(float(q),float(alpha),float(l1r),max_iter=1000,tol=2e-6,enet_max_iter=1500,enet_tol=1e-6).fit(Xrtr,yrtr,progress_callback=progress)
                        p=qm.predict(Xrte);qloss.append(pinball(yrte,p,float(q)))
                        if float(q)==0.5:median_pred=p
                        qtelemetry.append({"q":float(q),"iterations":qm.n_iter_,"converged":qm.converged_,"elapsed_seconds":qm.elapsed_seconds_,"matvec_seconds":qm.matvec_seconds_,"elastic_net_seconds":qm.elastic_net_seconds_,"prox_seconds":qm.prox_seconds_,"primal_residual_norm":qm.primal_residual_norm_,"dual_residual_norm":qm.dual_residual_norm_})
                        print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} q={q} DONE iterations={qm.n_iter_} converged={qm.converged_} elapsed={qm.elapsed_seconds_:.1f}s",flush=True)
                    medae=float(np.median(np.abs(yrte-median_pred)))
                    dacc=float(np.mean((yrte>0)==(median_pred>0)))
                    evidence.append({"fold_id":fold["fold_id"],"horizon":h,"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","status":"EVALUATED","alpha":alpha,"l1_ratio":l1r,"train_count":len(rtr),"test_count":len(rte),"mean_pinball_loss":float(np.mean(qloss)),"median_absolute_error":medae,"directional_accuracy_from_median_sign":dacc,"elapsed_seconds":time.perf_counter()-t,"quantile_telemetry":qtelemetry})
                    config_done.add(cfg);save()
                    print(f"{fold['fold_id']} h{h} MF3 alpha={alpha} l1={l1r} DONE mean_pinball={np.mean(qloss):.8f} CHECKPOINT",flush=True)

            done.add(unit);save()
            print(f"{fold['fold_id']} h{h}: CHECKPOINT SAVED",flush=True)

    # Development-only config selection from walk-forward evidence.
    selections=[]
    for h in HORIZONS:
        mf2=defaultdict(list);mf3=defaultdict(list)
        for e in evidence:
            if e.get("status")!="EVALUATED" or e.get("horizon")!=h:continue
            if e["family"]=="MF2_MONOTONIC_GAM_DIRECTION":mf2[(e["spline_knots"],e["l2_penalty"])].append(e["balanced_accuracy"])
            elif e["family"]=="MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION":mf3[(e["alpha"],e["l1_ratio"])].append(e["mean_pinball_loss"])
        if mf2:
            vals=[(sum(v)/len(v),k,l,len(v)) for (k,l),v in mf2.items()]
            score,k,l,n=max(vals,key=lambda z:(z[0],-z[1],-z[2]))
            selections.append({"family":"MF2_MONOTONIC_GAM_DIRECTION","horizon":h,"selected_config":{"spline_knots":k,"l2_penalty":l},"mean_walk_forward_balanced_accuracy":score,"fold_count":n})
        if mf3:
            vals=[(sum(v)/len(v),a,r,len(v)) for (a,r),v in mf3.items()]
            loss,a0,r0,n=min(vals,key=lambda z:(z[0],z[1],z[2]))
            selections.append({"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","horizon":h,"selected_config":{"alpha":a0,"l1_ratio":r0},"mean_walk_forward_pinball_loss":loss,"fold_count":n})

    report={
        "version":VERSION,"status":"READY",
        "execution_authority_sha256":sha256_file(xp),"semantic_authority_sha256":sha256_file(sp),
        "training_gate_sha256":sha256_file(gp),"target_authority_sha256":sha256_file(tp),
        "development_only":True,"training_observation_count":len(rows),"raw_feature_column_count":len(feature_cols),
        "walk_forward_fold_count":len(folds),"evidence":evidence,"development_selected_configs":selections,
        "governance":{
            "preprocessing_fit_within_train_fold_only":True,"preprocessing_reused_within_fold_horizon":True,
            "target_session_purge_enforced":True,"checkpoint_resume_enabled":True,
            "MF1_retuning_performed":False,"validation_feature_matrix_opened":False,"validation_outcomes_opened":False,
            "final_holdout_feature_matrix_opened":False,"final_holdout_outcomes_opened":False,
            "production_model_change_authorized":False,"production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_8_7_6_COMPLETE_THREE_FAMILY_DEVELOPMENT_EVIDENCE_BEFORE_ANY_VALIDATION_OPEN",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    fields=sorted({k for e in evidence for k,v in e.items() if not isinstance(v,(dict,list))})
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(evidence)
    print("=== M77.19.8.7.6 DEVELOPMENT-ONLY MF2/MF3 WALK-FORWARD EVALUATION WITH CHECKPOINTS [M77.19.8.7.6.1] ===")
    print("status: READY")
    print("training_observation_count:",len(rows))
    print("walk_forward_fold_count:",len(folds))
    print("MF2_evidence_row_count:",sum(e.get("family")=="MF2_MONOTONIC_GAM_DIRECTION" for e in evidence))
    print("MF3_evidence_row_count:",sum(e.get("family")=="MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION" for e in evidence))
    print("development_selected_configs:",selections)
    print("checkpoint_resume_enabled: True")
    print("validation_outcomes_opened: False")
    print("final_holdout_outcomes_opened: False")
    print("MF1_retuning_performed: False")
    print("production_authority_effect: False")
    print("next_step: REVIEW_M77_19_8_7_6_COMPLETE_THREE_FAMILY_DEVELOPMENT_EVIDENCE_BEFORE_ANY_VALIDATION_OPEN")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
