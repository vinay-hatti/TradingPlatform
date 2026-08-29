#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,tempfile,time
from collections import defaultdict
from pathlib import Path
import numpy as np

VERSION="M77.19.8.7.8-MF2-ONLY-DEVELOPMENT-WALK-FORWARD-COMPLETION-CHECKPOINT-REUSE-1.0"
EXPECTED_877_VERSION="M77.19.8.7.7-MF3-CANARY-CLOSURE-MF2-DEVELOPMENT-ONLY-CONTINUATION-AUTHORITY-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"
EXPECTED_85_VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
HORIZONS=[5,10,20]

class EvaluationError(RuntimeError):pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
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
            feats.pop("F071",None);feature_cols.update(feats)
            row={"symbol":symbol,"as_of":d,**feats}
            for h in HORIZONS:
                t=(tmap[d].get("targets") or {}).get(str(h)) or {}
                row[f"h{h}_status"]=t.get("status")
                row[f"h{h}_direction"]=t.get("direction_label")
                row[f"h{h}_target_session"]=t.get("target_session")
            rows.append(row)
    if len(rows)!=303689:raise EvaluationError(f"Development row count changed: {len(rows)}")
    return rows,sorted(feature_cols)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--continuation-authority-json",default="reports/m77_19_8_7_7_mf3_canary_closure_mf2_development_only_continuation_authority.json")
    ap.add_argument("--semantic-authority-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--feature-matrix-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_6_walk_forward_checkpoint.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_8_mf2_walk_forward_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    apath=resolve(root,a.continuation_authority_json);gpath=resolve(root,a.training_gate_json);tpath=resolve(root,a.target_authority_json)
    auth=load_json(apath);gate=load_json(gpath);ta=load_json(tpath)
    if auth.get("version")!=EXPECTED_877_VERSION or auth.get("status")!="READY":raise EvaluationError("M77.19.8.7.7 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise EvaluationError("M77.19.8.6 gate invalid")
    if ta.get("version")!=EXPECTED_85_VERSION or ta.get("status")!="READY":raise EvaluationError("M77.19.8.5 authority invalid")
    if auth.get("MF2_development_continuation_authorized") is not True:raise EvaluationError("MF2 continuation not authorized")
    if auth.get("MF3_rescue_search_authorized") is not False:raise EvaluationError("MF3 closure violated")
    if auth.get("validation_open_authorized") is not False or auth.get("final_holdout_open_authorized") is not False:raise EvaluationError("sealed partitions violated")

    from trading_ai.research.m77.m77_19_8_7_4_certified_solvers import CertifiedMonotonicGAM

    sign_map={}
    sign_csv=resolve(root,a.semantic_authority_csv)
    with sign_csv.open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):sign_map[r["column_name"]]=int(r["monotonic_sign"])

    print("Loading frozen Development matrix...",flush=True)
    rows,feature_cols=load_rows(resolve(root,a.feature_matrix_root),resolve(root,a.target_root),resolve(root,a.replay_root),gate)
    print(f"Development rows={len(rows)} raw_feature_columns={len(feature_cols)}",flush=True)

    folds=gate.get("walk_forward_preregistration",{}).get("folds") or []
    fam=gate.get("model_family_preregistration") or {}
    mf2_grid=fam["MF2_MONOTONIC_GAM_DIRECTION"]["fixed_grid"]

    checkpoint=resolve(root,a.checkpoint_json)
    evidence=[];config_done=set()
    if checkpoint.exists():
        ck=load_json(checkpoint)
        for e in ck.get("evidence") or []:
            if e.get("family")=="MF2_MONOTONIC_GAM_DIRECTION":
                evidence.append(e)
        config_done={tuple(x) for x in (ck.get("completed_configs") or []) if x and x[0]=="MF2"}
    expected_total=len(folds)*len(HORIZONS)*len(mf2_grid["spline_knots"])*len(mf2_grid["l2_penalty"])
    print(f"Existing MF2 completed configs={len(config_done)} expected_total={expected_total}",flush=True)

    def save_checkpoint():
        base={}
        if checkpoint.exists():
            base=load_json(checkpoint)
        other_e=[e for e in base.get("evidence") or [] if e.get("family")!="MF2_MONOTONIC_GAM_DIRECTION"]
        other_cfg=[x for x in base.get("completed_configs") or [] if not x or x[0]!="MF2"]
        base["evidence"]=other_e+evidence
        base["completed_configs"]=other_cfg+[list(x) for x in sorted(config_done)]
        base["validation_opened"]=False;base["final_holdout_opened"]=False;base["production_authority_effect"]=False
        atomic_json(checkpoint,base)

    for h in HORIZONS:
        for fold in folds:
            ts=fold["test_start"];te=fold["test_end"]
            needed=[]
            for knots in mf2_grid["spline_knots"]:
                for l2 in mf2_grid["l2_penalty"]:
                    cfg=("MF2",fold["fold_id"],h,str(knots),str(l2))
                    if cfg not in config_done:needed.append((knots,l2,cfg))
            if not needed:
                print(f"{fold['fold_id']} h{h}: ALL MF2 CONFIGS ALREADY COMPLETE",flush=True)
                continue

            dtr=[r for r in rows if r["as_of"]<ts and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_target_session"]<ts and r[f"h{h}_direction"] in ("UP","DOWN")]
            dte=[r for r in rows if ts<=r["as_of"]<=te and r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")]
            print(f"{fold['fold_id']} h{h}: train={len(dtr)} test={len(dte)} PREPROCESS remaining_configs={len(needed)}",flush=True)
            prep=FoldPreprocessor().fit(dtr,feature_cols,sign_map)
            Xtr=prep.transform(dtr);Xte=prep.transform(dte)
            ytr=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in dtr],dtype=float)
            yte=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in dte],dtype=int)

            for knots,l2,cfg in needed:
                t=time.perf_counter()
                print(f"{fold['fold_id']} h{h} MF2 knots={knots} l2={l2} START",flush=True)
                m=CertifiedMonotonicGAM(knot_count=int(knots),l2_penalty=float(l2),max_iter=300).fit(Xtr,ytr,prep.output_signs)
                prob=m.predict_proba(Xte)[:,1];pred=(prob>=.5).astype(int)
                bal=balanced_accuracy(yte,pred)
                evidence.append({
                    "fold_id":fold["fold_id"],"horizon":h,"family":"MF2_MONOTONIC_GAM_DIRECTION",
                    "status":"EVALUATED","spline_knots":knots,"l2_penalty":l2,
                    "train_count":len(dtr),"test_count":len(dte),"balanced_accuracy":bal,
                    "elapsed_seconds":time.perf_counter()-t
                })
                config_done.add(cfg);save_checkpoint()
                print(f"{fold['fold_id']} h{h} MF2 knots={knots} l2={l2} DONE bal_acc={bal:.6f} CHECKPOINT",flush=True)

    if len(config_done)!=expected_total:
        raise EvaluationError(f"MF2 completion incomplete: {len(config_done)}/{expected_total}")

    by_h=defaultdict(lambda:defaultdict(list))
    for e in evidence:
        if e.get("status")=="EVALUATED":
            by_h[int(e["horizon"])][(int(e["spline_knots"]),float(e["l2_penalty"]))].append(float(e["balanced_accuracy"]))

    selected=[];stability=[]
    for h in HORIZONS:
        vals=[]
        for (k,l),scores in by_h[h].items():
            if len(scores)!=len(folds):raise EvaluationError(f"h{h} config {k}/{l} has {len(scores)} folds")
            mean=float(np.mean(scores));std=float(np.std(scores));mn=float(np.min(scores));mx=float(np.max(scores))
            vals.append((mean,-std,-k,-l,k,l,scores,mn,mx))
            stability.append({"horizon":h,"spline_knots":k,"l2_penalty":l,"fold_count":len(scores),"mean_balanced_accuracy":mean,"std_balanced_accuracy":std,"min_balanced_accuracy":mn,"max_balanced_accuracy":mx})
        best=max(vals,key=lambda x:(x[0],x[1],x[2],x[3]))
        selected.append({
            "family":"MF2_MONOTONIC_GAM_DIRECTION","horizon":h,
            "selected_config":{"spline_knots":best[4],"l2_penalty":best[5]},
            "mean_walk_forward_balanced_accuracy":best[0],
            "std_walk_forward_balanced_accuracy":-best[1],
            "fold_balanced_accuracies":best[6],
            "fold_count":len(best[6]),
        })

    report={
        "version":VERSION,"status":"READY",
        "continuation_authority_sha256":sha256_file(apath),"training_gate_sha256":sha256_file(gpath),"target_authority_sha256":sha256_file(tpath),
        "development_only":True,"training_observation_count":len(rows),"raw_feature_column_count":len(feature_cols),
        "MF2_expected_config_evaluation_count":expected_total,
        "MF2_completed_config_evaluation_count":len(config_done),
        "MF2_existing_checkpoint_reuse_count":auth.get("MF2_existing_completed_config_checkpoint_count",0),
        "MF2_walk_forward_evidence":evidence,
        "MF2_config_stability":stability,
        "MF2_development_selected_configs":selected,
        "MF1_retuning_performed":False,
        "MF3_execution_performed":False,
        "MF3_rescue_search_performed":False,
        "model_family_champion_selected":False,
        "validation_opened":False,"final_holdout_opened":False,
        "production_model_change_authorized":False,"production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_9_MF1_VS_MF2_DEVELOPMENT_EVIDENCE_STABILITY_AND_VALIDATION_ADVANCEMENT_GATE",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    fields=sorted({k for e in evidence for k,v in e.items() if not isinstance(v,(dict,list))})
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(evidence)

    print("=== M77.19.8.7.8 MF2-ONLY DEVELOPMENT WALK-FORWARD COMPLETION WITH CHECKPOINT REUSE ===")
    print("status: READY")
    print("MF2_expected_config_evaluation_count:",expected_total)
    print("MF2_completed_config_evaluation_count:",len(config_done))
    print("MF2_existing_checkpoint_reuse_count:",auth.get("MF2_existing_completed_config_checkpoint_count",0))
    print("MF2_development_selected_configs:",selected)
    print("MF1_retuning_performed: False")
    print("MF3_execution_performed: False")
    print("MF3_rescue_search_performed: False")
    print("model_family_champion_selected: False")
    print("validation_opened: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_9_MF1_VS_MF2_DEVELOPMENT_EVIDENCE_STABILITY_AND_VALIDATION_ADVANCEMENT_GATE")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
