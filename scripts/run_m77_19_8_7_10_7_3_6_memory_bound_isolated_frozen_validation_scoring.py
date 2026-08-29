#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,os,subprocess,sys,tempfile
from pathlib import Path
import numpy as np

VERSION="M77.19.8.7.10.7.3.6-MEMORY-BOUND-ISOLATED-FROZEN-VALIDATION-SCORING-1.0"
OLD_VERSION="M77.19.8.7.10.7.3.5-REPO-GROUNDED-FROZEN-MF1-MF2-VALIDATION-SCORING-1.0"
HORIZONS=(5,10,20);MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION";MF2="MF2_MONOTONIC_GAM_DIRECTION"
class OrchestrationError(RuntimeError):pass
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def checkpoint(path,evidence,done,status="IN_PROGRESS"):
    atomic_json(path,{"version":VERSION,"status":status,"evidence":evidence,"completed_units":[list(x) for x in sorted(done)],"validation_scoring_performed":status=="COMPLETE","validation_model_retuning_performed":False,"final_holdout_opened":False,"production_authority_effect":False})
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--worker-script",default="scripts/run_m77_19_8_7_10_7_3_6_validation_scoring_unit_worker.py")
    ap.add_argument("--combined-invocation-json",default="reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json");ap.add_argument("--target-binding-json",default="reports/m77_19_8_7_10_7_3_4_target_status_eligibility_direction_label_binding_authority.json");ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json");ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json");ap.add_argument("--validation-target-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill");ap.add_argument("--development-target-root",default="research_data/m77_19_8_5/development_target_matrix");ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill");ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix");ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py");ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py");ap.add_argument("--mf2-runtime-module",default="src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py");ap.add_argument("--mf2-sign-registry-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_10_7_3_5_validation_scoring_checkpoint.json");ap.add_argument("--prediction-chunk-size",type=int,default=20000)
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_3_6_memory_bound_isolated_frozen_validation_scoring.json");ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_3_6_validation_scoring_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve();combined=load_json(resolve(root,a.combined_invocation_json));binding=load_json(resolve(root,a.target_binding_json))
    if combined.get("status")!="READY" or combined.get("combined_exact_invocation_authority_certified") is not True:raise OrchestrationError("combined invocation authority invalid")
    if binding.get("status")!="READY" or binding.get("validation_scoring_execution_authorized") is not True:raise OrchestrationError("target binding authority invalid")
    if combined.get("final_holdout_open_authorized") is not False or combined.get("model_family_champion_selection_authorized") is not False:raise OrchestrationError("sealed governance relaxed")
    cp=resolve(root,a.checkpoint_json);e=[];done=set()
    if cp.exists():
        old=load_json(cp)
        if old.get("version") not in (OLD_VERSION,VERSION):raise OrchestrationError(f"unsupported checkpoint version {old.get('version')}")
        e=list(old.get("evidence") or []);done={tuple(x) for x in old.get("completed_units") or []}
        print(f"CHECKPOINT RESUME: source_version={old.get('version')} completed_units={len(done)}",flush=True)
        checkpoint(cp,e,done)
    units=[(MF1,5),(MF2,5),(MF1,10),(MF2,10),(MF1,20),(MF2,20)]
    worker=resolve(root,a.worker_script)
    for family,h in units:
        unit=(family,h)
        if unit in done:
            print(f"{family} h{h}: SKIP COMPLETED",flush=True);continue
        result=resolve(root,f"reports/m77_19_8_7_10_7_3_6_unit_{'mf1' if family==MF1 else 'mf2'}_h{h}.json")
        if result.exists():result.unlink()
        cmd=[sys.executable,str(worker),"--project-root",str(root),"--family",family,"--horizon",str(h),
             "--training-gate-json",a.training_gate_json,"--development-target-authority-json",a.development_target_authority_json,"--validation-target-authority-json",a.validation_target_authority_json,
             "--development-feature-root",a.development_feature_root,"--development-target-root",a.development_target_root,"--validation-feature-root",a.validation_feature_root,"--validation-target-root",a.validation_target_root,"--replay-root",a.replay_root,
             "--mf1-development-script",a.mf1_development_script,"--mf2-development-script",a.mf2_development_script,"--mf2-runtime-module",a.mf2_runtime_module,"--mf2-sign-registry-csv",a.mf2_sign_registry_csv,
             "--prediction-chunk-size",str(a.prediction_chunk_size),"--result-json",str(result)]
        print(f"{family} h{h}: START ISOLATED WORKER",flush=True)
        rc=subprocess.call(cmd,cwd=root)
        if rc!=0:
            raise OrchestrationError(f"{family} h{h}: isolated worker failed returncode={rc}; completed units remain checkpointed")
        if not result.exists():raise OrchestrationError(f"{family} h{h}: worker returned success but result missing")
        rec=load_json(result)
        if rec.get("family")!=family or int(rec.get("horizon",-1))!=h or rec.get("status")!="EVALUATED":raise OrchestrationError(f"{family} h{h}: result contract mismatch")
        e=[x for x in e if not (x.get("family")==family and int(x.get("horizon",-1))==h)];e.append(rec);done.add(unit);checkpoint(cp,e,done)
        print(f"{family} h{h}: CHECKPOINTED AND WORKER RELEASED",flush=True)
    expected=set(units)
    if done!=expected:raise OrchestrationError(f"incomplete units {sorted(expected-done)}")
    stability={}
    for family in (MF1,MF2):
        vals=np.asarray([x["balanced_accuracy"] for x in e if x["family"]==family],dtype=float)
        if len(vals)!=3:raise OrchestrationError(f"{family}: evidence count {len(vals)}")
        stability[family]={"mean_balanced_accuracy":float(vals.mean()),"std_balanced_accuracy":float(vals.std()),"min_balanced_accuracy":float(vals.min()),"positive_horizons":int((vals>0.5).sum()),"horizon_count":3}
    report={"version":VERSION,"status":"READY","execution_mode":"ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS","checkpoint_reused_from_10_7_3_5":True,"family_horizon_metrics":sorted(e,key=lambda x:(x["family"],x["horizon"])),"validation_stability_evidence":stability,"validation_scoring_performed":True,"validation_preprocessor_refit_performed":False,"validation_model_refit_performed":False,"validation_model_retuning_performed":False,"validation_threshold_search_performed":False,"validation_feature_selection_search_performed":False,"model_family_champion_selection_authorized":False,"model_family_champion_selected":False,"final_holdout_open_authorized":False,"final_holdout_opened":False,"production_authority_effect":False,"next_step":"BUILD_M77_19_8_7_10_7_4_VALIDATION_EVIDENCE_STABILITY_AND_FINAL_HOLDOUT_ADVANCEMENT_GATE"}
    atomic_json(resolve(root,a.output_json),report);fields=["family","horizon","development_fit_row_count","validation_score_row_count","C","spline_knots","l2_penalty","balanced_accuracy","log_loss","brier_score","roc_auc","elapsed_seconds","prediction_execution_mode","prediction_chunk_size"]
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for x in sorted(e,key=lambda x:(x["family"],x["horizon"])):w.writerow({k:x.get(k) for k in fields})
    checkpoint(cp,e,done,"COMPLETE")
    print("=== M77.19.8.7.10.7.3.6 MEMORY-BOUND ISOLATED FROZEN VALIDATION SCORING ===");print("status: READY");print("execution_mode: ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS")
    for x in sorted(e,key=lambda x:(x["family"],x["horizon"])):print(f"{x['family']} h{x['horizon']}: bal_acc={x['balanced_accuracy']:.9f} dev={x['development_fit_row_count']} val={x['validation_score_row_count']}")
    print("validation_stability_evidence:",stability);print("validation_scoring_performed: True");print("validation_model_retuning_performed: False");print("model_family_champion_selected: False");print("final_holdout_opened: False");print("production_authority_effect: False");print("next_step:",report["next_step"]);return 0
if __name__=="__main__":raise SystemExit(main())
