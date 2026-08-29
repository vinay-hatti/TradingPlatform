#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.7-MF3-CANARY-CLOSURE-MF2-DEVELOPMENT-ONLY-CONTINUATION-AUTHORITY-1.0"
EXPECTED_8764_VERSION="M77.19.8.7.6.4-SINGLE-REAL-WF1-H5-Q050-CANARY-FULL-DEVELOPMENT-REAUTHORIZATION-GATE-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"

class AuthorityError(RuntimeError): pass

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
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--mf3-canary-json",default="reports/m77_19_8_7_6_4_single_real_wf1_h5_q050_canary_full_development_reauthorization_gate.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_6_walk_forward_checkpoint.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_7_mf3_canary_closure_mf2_development_only_continuation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_7_model_family_continuation_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cp=resolve(root,a.mf3_canary_json);gp=resolve(root,a.training_gate_json)
    canary=load_json(cp);gate=load_json(gp)
    if canary.get("version")!=EXPECTED_8764_VERSION or canary.get("status")!="READY":raise AuthorityError("M77.19.8.7.6.4 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise AuthorityError("M77.19.8.6 gate invalid")
    if canary.get("decision")!="BLOCK_FULL_DEVELOPMENT_CANARY_OBJECTIVE":raise AuthorityError("MF3 closure requires failed real canary objective gate")
    if canary.get("full_development_walk_forward_authorized") is not False:raise AuthorityError("MF3 full Development unexpectedly authorized")
    if canary.get("validation_open_authorized") is not False or canary.get("final_holdout_open_authorized") is not False:raise AuthorityError("sealed partition governance violated")

    checkpoint=resolve(root,a.checkpoint_json)
    completed_mf2=[]
    if checkpoint.exists():
        ck=load_json(checkpoint)
        completed_mf2=[x for x in (ck.get("completed_configs") or []) if x and x[0]=="MF2"]

    fam=gate.get("model_family_preregistration") or {}
    mf2=fam.get("MF2_MONOTONIC_GAM_DIRECTION") or {}
    fixed_grid=mf2.get("fixed_grid") or {}
    folds=gate.get("walk_forward_preregistration",{}).get("folds") or []
    horizons=gate.get("walk_forward_preregistration",{}).get("horizons") or [5,10,20]

    rows=[
      {"family":"MF1_REGULARIZED_LOGISTIC_DIRECTION","state":"DEVELOPMENT_EVIDENCE_COMPLETE_FROZEN","development_continuation_authorized":False,"retuning_authorized":False,"validation_authorized":False},
      {"family":"MF2_MONOTONIC_GAM_DIRECTION","state":"DEVELOPMENT_CONTINUATION_AUTHORIZED","development_continuation_authorized":True,"retuning_authorized":False,"validation_authorized":False},
      {"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","state":"CLOSED_CURRENT_ARCHITECTURE_REAL_CANARY_FAILED","development_continuation_authorized":False,"retuning_authorized":False,"validation_authorized":False},
    ]
    report={
      "version":VERSION,"status":"READY",
      "mf3_canary_sha256":sha256_file(cp),"training_gate_sha256":sha256_file(gp),
      "MF1_state":"DEVELOPMENT_EVIDENCE_COMPLETE_FROZEN",
      "MF1_retuning_authorized":False,
      "MF2_state":"DEVELOPMENT_CONTINUATION_AUTHORIZED",
      "MF2_development_continuation_authorized":True,
      "MF2_frozen_grid":fixed_grid,
      "MF2_frozen_fold_ids":[x.get("fold_id") for x in folds],
      "MF2_frozen_horizons":horizons,
      "MF2_existing_completed_config_checkpoint_count":len(completed_mf2),
      "MF2_existing_completed_configs":completed_mf2,
      "MF3_state":"CLOSED_CURRENT_ARCHITECTURE_REAL_CANARY_FAILED",
      "MF3_canary_runtime_pass":canary.get("runtime_pass"),
      "MF3_canary_numerical_pass":canary.get("numerical_pass"),
      "MF3_canary_economic_sanity_pass":canary.get("economic_sanity_pass"),
      "MF3_canary_test_pinball_loss":canary.get("test_pinball_loss"),
      "MF3_canary_zero_model_test_pinball_loss":canary.get("zero_model_test_pinball_loss"),
      "MF3_canary_directional_accuracy_from_median_sign":canary.get("directional_accuracy_from_median_sign"),
      "MF3_rescue_search_authorized":False,
      "MF3_objective_change_authorized":False,
      "MF3_retuning_authorized":False,
      "model_family_champion_selected":False,
      "validation_open_authorized":False,
      "final_holdout_open_authorized":False,
      "production_model_change_authorized":False,
      "production_authority_effect":False,
      "next_step":"BUILD_M77_19_8_7_8_MF2_ONLY_DEVELOPMENT_WALK_FORWARD_COMPLETION_WITH_EXISTING_CHECKPOINT_REUSE",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.7 MF3 CANARY CLOSURE & MF2 DEVELOPMENT-ONLY CONTINUATION AUTHORITY ===")
    print("status: READY")
    print("MF1_state: DEVELOPMENT_EVIDENCE_COMPLETE_FROZEN")
    print("MF1_retuning_authorized: False")
    print("MF2_state: DEVELOPMENT_CONTINUATION_AUTHORIZED")
    print("MF2_development_continuation_authorized: True")
    print("MF2_frozen_grid:",fixed_grid)
    print("MF2_frozen_fold_ids:",[x.get("fold_id") for x in folds])
    print("MF2_frozen_horizons:",horizons)
    print("MF2_existing_completed_config_checkpoint_count:",len(completed_mf2))
    print("MF3_state: CLOSED_CURRENT_ARCHITECTURE_REAL_CANARY_FAILED")
    print("MF3_rescue_search_authorized: False")
    print("MF3_retuning_authorized: False")
    print("model_family_champion_selected: False")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_8_MF2_ONLY_DEVELOPMENT_WALK_FORWARD_COMPLETION_WITH_EXISTING_CHECKPOINT_REUSE")
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
