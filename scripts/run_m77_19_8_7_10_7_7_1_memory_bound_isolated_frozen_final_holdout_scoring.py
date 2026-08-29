#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,os,subprocess,sys,tempfile
from pathlib import Path
from statistics import fmean,pstdev

FAMILIES=("MF1_REGULARIZED_LOGISTIC_DIRECTION","MF2_MONOTONIC_GAM_DIRECTION");HORIZONS=(5,10,20)
class ScoringError(RuntimeError):pass
def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--authority-json",default="reports/m77_19_8_7_10_7_7_frozen_final_holdout_scoring_execution_authority.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--development-target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--final-holdout-feature-root",default="research_data/m77_19_8_7_10_7_6_1/final_holdout_feature_matrix_certified_backfill")
    ap.add_argument("--final-holdout-target-root",default="research_data/m77_19_8_7_10_7_6_2_1/final_holdout_target_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-runtime-module",default="src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py")
    ap.add_argument("--mf2-sign-registry-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    ap.add_argument("--worker-script",default="scripts/run_m77_19_8_7_10_7_7_1_final_holdout_scoring_worker.py")
    ap.add_argument("--prediction-chunk-size",type=int,default=20000)
    ap.add_argument("--checkpoint-json",default="reports/m77_19_8_7_10_7_7_1_final_holdout_scoring_checkpoint.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_7_1_memory_bound_isolated_frozen_final_holdout_scoring.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_7_1_final_holdout_scoring_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve();op=R(root,a.output_json);cp=R(root,a.checkpoint_json)
    if op.exists():
        prior=J(op)
        if prior.get("status")=="READY":raise ScoringError("FINAL_HOLDOUT_ALREADY_SCORED_SINGLE_USE_REEXECUTION_PROHIBITED")
    auth=J(R(root,a.authority_json))
    if auth.get("status")!="READY" or auth.get("single_use_final_holdout_scoring_authorized") is not True:raise ScoringError("10.7.7 authority invalid")
    if auth.get("final_holdout_scoring_performed") is not False or auth.get("model_family_champion_selection_authorized") is not False:raise ScoringError("10.7.7 execution boundary invalid")
    done={}; 
    if cp.exists():
        c=J(cp)
        if c.get("authority_version")!=auth.get("version"):raise ScoringError("checkpoint authority version mismatch")
        done={f"{x['family']}:{x['horizon']}":x for x in c.get("completed_units") or []}
        print(f"CHECKPOINT RESUME: completed_units={len(done)}",flush=True)
    workdir=R(root,"research_data/m77_19_8_7_10_7_7_1/worker_results");workdir.mkdir(parents=True,exist_ok=True)
    for h in HORIZONS:
        for fam in FAMILIES:
            key=f"{fam}:{h}"
            if key in done:
                print(f"{fam} h{h}: SKIP COMPLETED",flush=True);continue
            uj=workdir/f"{fam}_h{h}.json"
            cmd=[sys.executable,str(R(root,a.worker_script)),"--project-root",str(root),"--family",fam,"--horizon",str(h),
                 "--authority-json",a.authority_json,"--development-feature-root",a.development_feature_root,"--development-target-root",a.development_target_root,
                 "--final-holdout-feature-root",a.final_holdout_feature_root,"--final-holdout-target-root",a.final_holdout_target_root,"--replay-root",a.replay_root,
                 "--training-gate-json",a.training_gate_json,"--mf1-development-script",a.mf1_development_script,"--mf2-development-script",a.mf2_development_script,
                 "--mf2-runtime-module",a.mf2_runtime_module,"--mf2-sign-registry-csv",a.mf2_sign_registry_csv,
                 "--prediction-chunk-size",str(a.prediction_chunk_size),"--output-json",str(uj)]
            print(f"{fam} h{h}: START ISOLATED WORKER",flush=True)
            rc=subprocess.call(cmd,cwd=root)
            if rc!=0:raise ScoringError(f"{fam} h{h}: worker failed returncode={rc}")
            rec=J(uj)
            if rec.get("status")!="READY":raise ScoringError(f"{fam} h{h}: worker result invalid")
            done[key]=rec
            atomic(cp,{"version":"M77.19.8.7.10.7.7.1-CHECKPOINT-1.0","status":"IN_PROGRESS","authority_version":auth.get("version"),
                       "completed_units":[done[k] for k in sorted(done)],"final_holdout_scoring_complete":False,
                       "model_family_champion_selected":False,"production_authority_effect":False})
            print(f"{fam} h{h}: CHECKPOINTED AND WORKER RELEASED",flush=True)
    if len(done)!=6:raise ScoringError(f"incomplete holdout scoring {len(done)}/6")
    ev=[done[k] for k in sorted(done)]
    stability={}
    for fam in FAMILIES:
        vals=[x["metrics"]["balanced_accuracy"] for x in ev if x["family"]==fam]
        stability[fam]={"mean_balanced_accuracy":fmean(vals),"std_balanced_accuracy":pstdev(vals),"min_balanced_accuracy":min(vals),
                        "max_balanced_accuracy":max(vals),"above_chance_horizons":sum(v>0.5 for v in vals),"horizon_count":len(vals)}
    report={"version":"M77.19.8.7.10.7.7.1-MEMORY-BOUND-ISOLATED-FROZEN-FINAL-HOLDOUT-SCORING-1.0","status":"READY",
            "execution_mode":"ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS","single_use_final_holdout_scoring_consumed":True,
            "family_horizon_metrics":[{"family":x["family"],"horizon":x["horizon"],"config":x["config"],
               "development_binary_rows":x["development_binary_rows"],"final_holdout_binary_rows":x["final_holdout_binary_rows"],**x["metrics"]} for x in ev],
            "final_holdout_stability_evidence":stability,"final_holdout_scoring_performed":True,
            "development_only_fit":True,"validation_rows_used_for_fit":False,"final_holdout_rows_used_for_fit":False,
            "final_holdout_model_refit_performed":False,"final_holdout_preprocessor_refit_performed":False,"final_holdout_model_retuning_performed":False,
            "threshold_search_performed":False,"feature_selection_search_performed":False,"hyperparameter_search_performed":False,
            "automatic_pass_fail_rule_applied":False,"model_family_champion_selection_authorized":False,"model_family_champion_selected":False,
            "production_model_change_authorized":False,"production_authority_effect":False,
            "next_step":"BUILD_M77_19_8_7_10_7_8_FINAL_HOLDOUT_EVIDENCE_PUBLICATION_AND_RESEARCH_CLOSURE_GOVERNANCE"}
    atomic(op,report)
    with R(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["family","horizon","development_binary_rows","final_holdout_binary_rows","balanced_accuracy","log_loss","brier_score","roc_auc"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for x in report["family_horizon_metrics"]:w.writerow({k:x.get(k) for k in fields})
    atomic(cp,{"version":"M77.19.8.7.10.7.7.1-CHECKPOINT-1.0","status":"COMPLETE","authority_version":auth.get("version"),
               "completed_units":ev,"final_holdout_scoring_complete":True,"single_use_final_holdout_scoring_consumed":True,
               "model_family_champion_selected":False,"production_authority_effect":False})
    print("=== M77.19.8.7.10.7.7.1 MEMORY-BOUND ISOLATED FROZEN FINAL HOLDOUT SCORING ===")
    print("status: READY")
    for x in sorted(report["family_horizon_metrics"],key=lambda z:(z["family"],z["horizon"])):
        print(f"{x['family']} h{x['horizon']}: bal_acc={x['balanced_accuracy']:.9f} log_loss={x['log_loss']:.9f} brier={x['brier_score']:.9f} roc_auc={x['roc_auc']}")
    print("final_holdout_stability_evidence:",stability)
    print("single_use_final_holdout_scoring_consumed: True");print("final_holdout_scoring_performed: True")
    print("final_holdout_model_refit_performed: False");print("final_holdout_model_retuning_performed: False")
    print("automatic_pass_fail_rule_applied: False");print("model_family_champion_selected: False");print("production_authority_effect: False")
    print("next_step:",report["next_step"]);print("report:",op);print("csv:",R(root,a.output_csv))
if __name__=="__main__":main()
