#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path
import numpy as np
VERSION="M77.19.8.7.9-MF1-VS-MF2-DEVELOPMENT-EVIDENCE-STABILITY-VALIDATION-ADVANCEMENT-GATE-1.0"
EXPECTED_878_VERSION="M77.19.8.7.8-MF2-ONLY-DEVELOPMENT-WALK-FORWARD-COMPLETION-CHECKPOINT-REUSE-1.0"
class GateError(RuntimeError):pass
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
# M77.19.8.7.9.1-MF1-FOLD-EVIDENCE-SCHEMA-RECONSTRUCTION-REPAIR

def _walk_dicts(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from _walk_dicts(v)

def _cfg_matches_evidence(selected_config,evidence):
    if not isinstance(selected_config,dict):
        return True
    if evidence.get("family")!="MF1_REGULARIZED_LOGISTIC_DIRECTION":
        return False
    for k,v in selected_config.items():
        if k in evidence:
            try:
                if float(evidence[k])!=float(v):
                    return False
            except Exception:
                if evidence[k]!=v:
                    return False
    return True

def reconstruct_mf1_folds(mf1,rec):
    h=int(rec["horizon"])
    selected=rec.get("selected_config") or {}
    candidates=[]
    for d in _walk_dicts(mf1):
        if d is rec:
            continue
        if d.get("family")!="MF1_REGULARIZED_LOGISTIC_DIRECTION":
            continue
        try:
            dh=int(d.get("horizon"))
        except Exception:
            continue
        if dh!=h:
            continue
        if d.get("fold_id") not in ("WF1","WF2","WF3","WF4","WF5"):
            continue
        if d.get("balanced_accuracy") is None:
            continue
        if not _cfg_matches_evidence(selected,d):
            continue
        candidates.append(d)

    by_fold={}
    for d in candidates:
        fid=d["fold_id"]
        val=float(d["balanced_accuracy"])
        if fid in by_fold and abs(by_fold[fid]-val)>1e-12:
            raise GateError(f"MF1 h{h}: ambiguous balanced_accuracy for {fid} under selected config {selected}")
        by_fold[fid]=val

    ordered=[by_fold.get(fid) for fid in ("WF1","WF2","WF3","WF4","WF5")]
    if all(v is not None for v in ordered):
        return [float(v) for v in ordered]

    nested=[]
    for d in _walk_dicts(mf1):
        if d is rec:
            continue
        try:
            dh=int(d.get("horizon"))
        except Exception:
            continue
        if dh!=h or d.get("family")!="MF1_REGULARIZED_LOGISTIC_DIRECTION":
            continue
        if not _cfg_matches_evidence(selected,d):
            continue
        for key in ("fold_balanced_accuracies","fold_scores","walk_forward_fold_balanced_accuracies"):
            vals=d.get(key)
            if isinstance(vals,list) and len(vals)==5:
                try:
                    nested.append([float(x) for x in vals])
                except Exception:
                    pass
    if nested:
        first=nested[0]
        for x in nested[1:]:
            if any(abs(a-b)>1e-12 for a,b in zip(first,x)):
                raise GateError(f"MF1 h{h}: ambiguous nested five-fold evidence")
        return first

    raise GateError(
        f"MF1_REGULARIZED_LOGISTIC_DIRECTION h{h}: could not reconstruct five frozen folds "
        f"for selected_config={selected}; flattened_fold_ids={sorted(by_fold)}"
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--mf1-development-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_9_mf1_vs_mf2_development_evidence_stability_validation_advancement_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_9_model_family_horizon_advancement.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    p1=resolve(root,a.mf1_development_json);p2=resolve(root,a.mf2_development_json)
    mf1=load_json(p1);mf2=load_json(p2)
    if mf2.get("version")!=EXPECTED_878_VERSION or mf2.get("status")!="READY":raise GateError("M77.19.8.7.8 authority invalid")
    if mf2.get("MF3_execution_performed") is not False or mf2.get("validation_opened") is not False:raise GateError("MF2 governance violated")
    mf1_selected=mf1.get("MF1_development_selected_configs") or mf1.get("development_selected_configs") or []
    if not mf1_selected:mf1_selected=[x for x in (mf1.get("selected_configs") or []) if x.get("family")=="MF1_REGULARIZED_LOGISTIC_DIRECTION"]
    mf1_selected=[x for x in mf1_selected if x.get("family")=="MF1_REGULARIZED_LOGISTIC_DIRECTION"]
    mf2_selected=mf2.get("MF2_development_selected_configs") or []
    if len(mf1_selected)!=3 or len(mf2_selected)!=3:raise GateError(f"expected three horizon selections per family; MF1={len(mf1_selected)} MF2={len(mf2_selected)}")
    def norm(rec,family):
        h=int(rec["horizon"]);mean=float(rec["mean_walk_forward_balanced_accuracy"])
        folds=[float(x) for x in rec.get("fold_balanced_accuracies",[])]
        if len(folds)!=5 and family=="MF1_REGULARIZED_LOGISTIC_DIRECTION":
            folds=reconstruct_mf1_folds(mf1,rec)
        if len(folds)!=5:raise GateError(f"{family} h{h}: expected five folds")
        std=float(rec.get("std_walk_forward_balanced_accuracy",np.std(folds)));pos=sum(x>0.5 for x in folds);mn=min(folds)
        gates=(mean>=0.505,pos>=3,mn>=0.495,std<=0.015)
        return {"family":family,"horizon":h,"mean_balanced_accuracy":mean,"std_balanced_accuracy":std,
        "min_fold_balanced_accuracy":mn,"positive_fold_count":pos,"fold_count":5,
        "mean_gate_ge_0_505":gates[0],"positive_fold_gate_ge_3":gates[1],"minimum_fold_gate_ge_0_495":gates[2],
        "std_gate_le_0_015":gates[3],"development_advancement_pass":all(gates),
        "selected_config":rec.get("selected_config"),"fold_balanced_accuracies":folds}
    rows=[norm(x,"MF1_REGULARIZED_LOGISTIC_DIRECTION") for x in mf1_selected]+[norm(x,"MF2_MONOTONIC_GAM_DIRECTION") for x in mf2_selected]
    decisions={}
    for fam in ("MF1_REGULARIZED_LOGISTIC_DIRECTION","MF2_MONOTONIC_GAM_DIRECTION"):
        rr=[x for x in rows if x["family"]==fam];passed=[x["horizon"] for x in rr if x["development_advancement_pass"]]
        decisions[fam]={"passed_horizons":passed,"failed_horizons":[x["horizon"] for x in rr if not x["development_advancement_pass"]],"validation_advancement_authorized":bool(passed)}
    scope={k:v["passed_horizons"] for k,v in decisions.items() if v["validation_advancement_authorized"]}
    report={"version":VERSION,"status":"READY","mf1_development_sha256":sha256_file(p1),"mf2_development_sha256":sha256_file(p2),
    "development_advancement_criteria":{"minimum_mean_balanced_accuracy":0.505,"minimum_positive_fold_count":3,"minimum_single_fold_balanced_accuracy":0.495,"maximum_fold_std_balanced_accuracy":0.015,"criteria_frozen_before_validation_open":True},
    "family_horizon_evidence":rows,"family_decisions":decisions,"authorized_validation_scope":scope,
    "validation_outcomes_read":False,"validation_scoring_performed":False,"validation_open_authorized_for_scope_only":bool(scope),
    "final_holdout_open_authorized":False,"model_family_champion_selected":False,"MF1_retuning_authorized":False,
    "MF2_retuning_authorized":False,"MF3_reopened":False,"production_model_change_authorized":False,"production_authority_effect":False,
    "next_step":"BUILD_M77_19_8_7_10_AUTHORIZED_MODEL_FAMILY_VALIDATION_ONLY_EVALUATION" if scope else "CLOSE_M77_19_8_PROSPECTIVE_EDGE_MODEL_FAMILY_RESEARCH_NO_DEVELOPMENT_SURVIVOR"}
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    flat=[]
    for r in rows:
        x={k:v for k,v in r.items() if k not in ("selected_config","fold_balanced_accuracies")}
        x["selected_config"]=json.dumps(r["selected_config"],sort_keys=True);x["fold_balanced_accuracies"]=json.dumps(r["fold_balanced_accuracies"]);flat.append(x)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    print("=== M77.19.8.7.9 MF1 VS MF2 DEVELOPMENT EVIDENCE STABILITY & VALIDATION ADVANCEMENT GATE ===")
    print("status: READY")
    for r in rows:print(f"{r['family']} h{r['horizon']}: mean={r['mean_balanced_accuracy']} std={r['std_balanced_accuracy']} min={r['min_fold_balanced_accuracy']} positive_folds={r['positive_fold_count']}/5 advance={r['development_advancement_pass']}")
    print("authorized_validation_scope:",scope);print("validation_outcomes_read: False");print("validation_scoring_performed: False")
    print("final_holdout_open_authorized: False");print("model_family_champion_selected: False");print("MF3_reopened: False")
    print("production_authority_effect: False");print("next_step:",report["next_step"]);print("report:",oj);print("csv:",oc);return 0
if __name__=="__main__":raise SystemExit(main())
