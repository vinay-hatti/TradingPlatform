#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,importlib.util,json,os,sys,tempfile,time
from collections import Counter
from pathlib import Path
import numpy as np
VERSION="M77.19.8.7.10.7.3.5-REPO-GROUNDED-FROZEN-MF1-MF2-VALIDATION-SCORING-1.0"
HORIZONS=(5,10,20);MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION";MF2="MF2_MONOTONIC_GAM_DIRECTION";DEV_END="2017-12-31";VAL_START="2018-01-01";VAL_END="2022-12-31"
FROZEN_MF1={5:{"C":10.0},10:{"C":1.0},20:{"C":0.1}};FROZEN_MF2={5:{"spline_knots":4,"l2_penalty":0.1},10:{"spline_knots":4,"l2_penalty":0.1},20:{"spline_knots":4,"l2_penalty":0.1}}
class ScoringError(RuntimeError):pass
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def iter_jsonl_gz(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def import_module(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:raise ScoringError(f"cannot import {path}")
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def load_sign_map(path):
    out={}
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):out[r["column_name"]]=int(r["monotonic_sign"])
    if not out:raise ScoringError("MF2 sign map empty")
    return out
def s106(a):
    rows=a.get("target_horizon_summary")
    if not isinstance(rows,list):raise ScoringError("10.6 summary schema invalid")
    out={int(x["horizon"]):x for x in rows}
    if set(out)!=set(HORIZONS):raise ScoringError("10.6 horizons mismatch")
    return out
def load_dev(fr,tr,rr,gate,mf1):
    ff={p.name[:-9]:p for p in Path(fr).glob("*.jsonl.gz")};tf={p.name[:-9]:p for p in Path(tr).glob("*.jsonl.gz")};rf={p.name[:-9]:p for p in (Path(rr)/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(ff)!=524 or len(tf)!=524:raise ScoringError(f"Development cardinality {len(ff)}/{len(tf)}")
    rows=[];cols=set()
    for sym in sorted(ff):
        if sym not in tf or sym not in rf:raise ScoringError(f"Development source missing {sym}")
        fm={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(ff[sym])};tm={str(x["as_of"])[:10]:x for x in iter_jsonl_gz(tf[sym])};rm={}
        for x in iter_jsonl_gz(rf[sym]):
            d=str(x.get("as_of") or "")[:10]
            if d<=DEV_END and x.get("status")=="REPLAYED":rm[d]=x
        if set(fm)!=set(tm):raise ScoringError(f"{sym}: feature/target keys differ")
        for d in sorted(fm):
            r=rm.get(d)
            if r is None:raise ScoringError(f"{sym} {d}: Development replay provenance missing")
            feats=mf1.flatten_base_features(fm[d].get("feature_values") or {});feats.update(mf1.build_structured(r.get("profile") or {},gate));feats.pop("F071",None);cols.update(feats)
            row={"symbol":sym,"as_of":d,**feats};targets=tm[d].get("targets") or {}
            for h in HORIZONS:
                t=targets.get(str(h)) or {};row[f"h{h}_status"]=t.get("status");row[f"h{h}_direction"]=t.get("direction_label");row[f"h{h}_target_session"]=t.get("target_session")
            rows.append(row)
    if len(rows)!=303689:raise ScoringError(f"Development row count {len(rows)}")
    c=sorted(cols)
    if any("F071" in x for x in c):raise ScoringError("F071 leak")
    return rows,c
def load_val_targets(root,a106):
    ex=s106(a106);maps={h:{} for h in HORIZONS};counts={h:Counter() for h in HORIZONS}
    for h in HORIZONS:
        files=sorted((Path(root)/f"h{h}").glob("*.jsonl.gz"))
        if not files:raise ScoringError(f"h{h} Validation target dir empty")
        for p in files:
            for r in iter_jsonl_gz(p):
                if int(r.get("horizon_sessions",-1))!=h or r.get("partition")!="VALIDATION":raise ScoringError(f"{p}: target contract mismatch")
                lab=r.get("T_DIRECTION")
                if lab not in ("UP","DOWN","ZERO"):raise ScoringError(f"{p}: bad T_DIRECTION")
                k=(r["symbol"],str(r["as_of"])[:10])
                if k in maps[h]:raise ScoringError(f"duplicate target {k} h{h}")
                maps[h][k]=r;counts[h][lab]+=1
        if len(maps[h])!=int(ex[h]["matured"]):raise ScoringError(f"h{h}: target count mismatch")
        if {k:counts[h][k] for k in ("UP","DOWN","ZERO")}!={k:int(ex[h][k]) for k in ("UP","DOWN","ZERO")}:raise ScoringError(f"h{h}: labels mismatch")
    return maps
def load_val(fr,rr,gate,mf1,target_maps,dev_cols):
    ff={p.name[:-9]:p for p in Path(fr).glob("*.jsonl.gz")};rf={p.name[:-9]:p for p in (Path(rr)/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(ff)!=570:raise ScoringError(f"Validation symbol count {len(ff)}")
    rows=[];seen=set()
    for sym in sorted(ff):
        if sym not in rf:raise ScoringError(f"Validation replay missing {sym}")
        rm={}
        for x in iter_jsonl_gz(rf[sym]):
            d=str(x.get("as_of") or "")[:10]
            if VAL_START<=d<=VAL_END and x.get("status")=="REPLAYED":rm[d]=x
        for frow in iter_jsonl_gz(ff[sym]):
            d=str(frow.get("as_of") or "")[:10]
            if not (VAL_START<=d<=VAL_END):raise ScoringError(f"{sym} {d}: outside Validation")
            r=rm.get(d)
            if r is None:raise ScoringError(f"{sym} {d}: Validation replay provenance missing")
            feats=mf1.flatten_base_features(frow.get("feature_values") or {});feats.update(mf1.build_structured(r.get("profile") or {},gate));feats.pop("F071",None);seen.update(feats)
            row={"symbol":sym,"as_of":d,**feats}
            for h in HORIZONS:
                t=target_maps[h].get((sym,d));row[f"h{h}_status"]="MATURED" if t else "NOT_IN_MATURED_VALIDATION_TARGET_MATRIX";row[f"h{h}_direction"]=None if not t else t["T_DIRECTION"];row[f"h{h}_target_session"]=None if not t else t["target_session"]
            rows.append(row)
    if len(rows)!=141567:raise ScoringError(f"Validation row count {len(rows)}")
    extra=seen-set(dev_cols)
    if extra:raise ScoringError(f"Validation-only feature columns {sorted(extra)[:10]}")
    return rows
def save_cp(p,e,c):
    atomic_json(p,{"version":VERSION,"status":"IN_PROGRESS","evidence":e,"completed_units":[list(x) for x in sorted(c)],"validation_scoring_in_progress":True,"validation_model_retuning_performed":False,"final_holdout_opened":False,"production_authority_effect":False})
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--combined-invocation-json",default="reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json");ap.add_argument("--target-binding-json",default="reports/m77_19_8_7_10_7_3_4_target_status_eligibility_direction_label_binding_authority.json");ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json");ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json");ap.add_argument("--validation-target-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill");ap.add_argument("--development-target-root",default="research_data/m77_19_8_5/development_target_matrix");ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill");ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix");ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py");ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py");ap.add_argument("--mf2-runtime-module",default="src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py");ap.add_argument("--mf2-sign-registry-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_10_7_3_5_validation_scoring_checkpoint.json");ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_3_5_repo_grounded_frozen_mf1_mf2_validation_scoring.json");ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_3_5_validation_scoring_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve();combined=load_json(resolve(root,a.combined_invocation_json));binding=load_json(resolve(root,a.target_binding_json));gate=load_json(resolve(root,a.training_gate_json));a85=load_json(resolve(root,a.development_target_authority_json));a106=load_json(resolve(root,a.validation_target_authority_json))
    if combined.get("status")!="READY" or combined.get("combined_exact_invocation_authority_certified") is not True:raise ScoringError("combined invocation invalid")
    if binding.get("status")!="READY" or binding.get("target_status_eligibility_binding_certified") is not True or binding.get("validation_scoring_execution_authorized") is not True:raise ScoringError("target binding invalid")
    if combined.get("final_holdout_open_authorized") is not False or combined.get("model_family_champion_selection_authorized") is not False:raise ScoringError("sealed governance relaxed")
    if combined.get("frozen_MF1_selected_configs")!={str(h):FROZEN_MF1[h] for h in HORIZONS}:raise ScoringError("MF1 config changed")
    if combined.get("frozen_MF2_selected_configs")!={str(h):FROZEN_MF2[h] for h in HORIZONS}:raise ScoringError("MF2 config changed")
    mf1=import_module("m77_8735_mf1",resolve(root,a.mf1_development_script));mf2=import_module("m77_8735_mf2",resolve(root,a.mf2_development_script));rt=import_module("m77_8735_rt",resolve(root,a.mf2_runtime_module));FP=getattr(mf2,"FoldPreprocessor");GAM=getattr(rt,"CertifiedMonotonicGAM");ml=mf1.require_ml();sign=load_sign_map(resolve(root,a.mf2_sign_registry_csv))
    print("Loading repo-grounded Development structured matrix...",flush=True);dev,cols=load_dev(resolve(root,a.development_feature_root),resolve(root,a.development_target_root),resolve(root,a.replay_root),gate,mf1);print(f"Development rows={len(dev)} model_feature_columns={len(cols)}",flush=True)
    print("Loading certified Validation targets...",flush=True);vt=load_val_targets(resolve(root,a.validation_target_root),a106);print("Validation targets:",{h:len(vt[h]) for h in HORIZONS},flush=True)
    print("Loading repo-grounded Validation structured matrix...",flush=True);val=load_val(resolve(root,a.validation_feature_root),resolve(root,a.replay_root),gate,mf1,vt,cols);print(f"Validation rows={len(val)}",flush=True)
    cp=resolve(root,a.checkpoint_json);e=[];done=set()
    if cp.exists():
        x=load_json(cp)
        if x.get("version")!=VERSION:raise ScoringError("checkpoint version mismatch")
        e=list(x.get("evidence") or []);done={tuple(z) for z in x.get("completed_units") or []};print(f"RESUME completed={len(done)}",flush=True)
    for h in HORIZONS:
        d=[r for r in dev if r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")];v=[r for r in val if r[f"h{h}_status"]=="MATURED" and r[f"h{h}_direction"] in ("UP","DOWN")]
        de=a85["target_matrix"]["horizon_summary"][str(h)]["direction_labels"];ve=s106(a106)[h]
        if len(d)!=int(de["UP"])+int(de["DOWN"]) or len(v)!=int(ve["UP"])+int(ve["DOWN"]):raise ScoringError(f"h{h}: binary cardinality mismatch")
        u=(MF1,h)
        if u not in done:
            c=FROZEN_MF1[h];t=time.perf_counter();recs=mf1.evaluate_mf1(d,v,cols,f"h{h}_direction",{"C":[c["C"]]},ml,progress_prefix=f"VALIDATION MF1 h{h}")
            if len(recs)!=1 or float(recs[0]["C"])!=float(c["C"]):raise ScoringError("MF1 evidence mismatch")
            e.append({"family":MF1,"horizon":h,"status":"EVALUATED","development_fit_row_count":len(d),"validation_score_row_count":len(v),"elapsed_seconds":time.perf_counter()-t,**recs[0]});done.add(u);save_cp(cp,e,done);print(f"MF1 h{h}: CHECKPOINT",flush=True)
        else:print(f"MF1 h{h}: SKIP COMPLETED",flush=True)
        u=(MF2,h)
        if u not in done:
            c=FROZEN_MF2[h];t=time.perf_counter();prep=FP().fit(d,cols,sign);Xtr=prep.transform(d);Xv=prep.transform(v);ytr=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in d],dtype=float);yv=np.asarray([1 if r[f"h{h}_direction"]=="UP" else 0 for r in v],dtype=int);m=GAM(knot_count=c["spline_knots"],l2_penalty=c["l2_penalty"],max_iter=300).fit(Xtr,ytr,prep.output_signs);prob=m.predict_proba(Xv)[:,1];pred=(prob>=0.5).astype(int);bal=float(ml["balanced_accuracy_score"](yv,pred));ll=float(ml["log_loss"](yv,prob,labels=[0,1]));br=float(ml["brier_score_loss"](yv,prob))
            try:auc=float(ml["roc_auc_score"](yv,prob))
            except Exception:auc=None
            e.append({"family":MF2,"horizon":h,"status":"EVALUATED","development_fit_row_count":len(d),"validation_score_row_count":len(v),"spline_knots":c["spline_knots"],"l2_penalty":c["l2_penalty"],"balanced_accuracy":bal,"log_loss":ll,"brier_score":br,"roc_auc":auc,"elapsed_seconds":time.perf_counter()-t});done.add(u);save_cp(cp,e,done);print(f"MF2 h{h}: CHECKPOINT",flush=True)
        else:print(f"MF2 h{h}: SKIP COMPLETED",flush=True)
    expected={(f,h) for f in (MF1,MF2) for h in HORIZONS}
    if done!=expected:raise ScoringError("incomplete scoring")
    stability={}
    for f in (MF1,MF2):
        vals=np.asarray([x["balanced_accuracy"] for x in e if x["family"]==f]);stability[f]={"mean_balanced_accuracy":float(vals.mean()),"std_balanced_accuracy":float(vals.std()),"min_balanced_accuracy":float(vals.min()),"positive_horizons":int((vals>0.5).sum()),"horizon_count":3}
    report={"version":VERSION,"status":"READY","model_feature_column_count":len(cols),"development_observation_count":len(dev),"validation_observation_count":len(val),"frozen_MF1_selected_configs":{str(h):FROZEN_MF1[h] for h in HORIZONS},"frozen_MF2_selected_configs":{str(h):FROZEN_MF2[h] for h in HORIZONS},"family_horizon_metrics":sorted(e,key=lambda x:(x["family"],x["horizon"])),"validation_stability_evidence":stability,"development_preprocessor_fit_performed_for_validation_execution":True,"development_model_fit_performed_for_validation_execution":True,"validation_scoring_performed":True,"validation_preprocessor_refit_performed":False,"validation_model_refit_performed":False,"validation_model_retuning_performed":False,"validation_threshold_search_performed":False,"validation_feature_selection_search_performed":False,"model_family_champion_selection_authorized":False,"model_family_champion_selected":False,"final_holdout_open_authorized":False,"final_holdout_feature_rows_opened":False,"final_holdout_targets_opened":False,"final_holdout_outcomes_opened":False,"production_authority_effect":False,"next_step":"BUILD_M77_19_8_7_10_7_4_VALIDATION_EVIDENCE_STABILITY_AND_FINAL_HOLDOUT_ADVANCEMENT_GATE"}
    atomic_json(resolve(root,a.output_json),report)
    fields=["family","horizon","development_fit_row_count","validation_score_row_count","C","spline_knots","l2_penalty","balanced_accuracy","log_loss","brier_score","roc_auc","elapsed_seconds"]
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for x in sorted(e,key=lambda x:(x["family"],x["horizon"])):w.writerow({k:x.get(k) for k in fields})
    atomic_json(cp,{"version":VERSION,"status":"COMPLETE","completed_units":[list(x) for x in sorted(done)],"evidence":e,"validation_scoring_performed":True,"final_holdout_opened":False,"production_authority_effect":False})
    print("=== M77.19.8.7.10.7.3.5 REPO-GROUNDED FROZEN MF1/MF2 VALIDATION SCORING ===");print("status: READY");print("model_feature_column_count:",len(cols))
    for x in sorted(e,key=lambda x:(x["family"],x["horizon"])):print(f"{x['family']} h{x['horizon']}: dev_fit={x['development_fit_row_count']} validation={x['validation_score_row_count']} bal_acc={x['balanced_accuracy']:.9f} log_loss={x['log_loss']:.9f} brier={x['brier_score']:.9f} roc_auc={x.get('roc_auc')}")
    print("validation_stability_evidence:",stability);print("validation_scoring_performed: True");print("validation_preprocessor_refit_performed: False");print("validation_model_refit_performed: False");print("validation_model_retuning_performed: False");print("model_family_champion_selected: False");print("final_holdout_opened: False");print("production_authority_effect: False");print("next_step:",report["next_step"]);print("report:",resolve(root,a.output_json));print("csv:",resolve(root,a.output_csv));print("checkpoint:",cp);return 0
if __name__=="__main__":raise SystemExit(main())
