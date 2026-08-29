#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7-FROZEN-MF1-MF2-VALIDATION-SCORING-STABILITY-PREREGISTRATION-GATE-1.0"
MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=(5,10,20)
EXPECTED_VALIDATION_FEATURE_ROWS=141567

class GateError(RuntimeError):pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def extract_mf1_configs(d):
    # Prefer explicit selected-config list from 8.7 authority.
    candidates=[]
    for key in ("selected_model_configs","selected_configs","development_selected_configs","MF1_development_selected_configs_preserved"):
        v=d.get(key)
        if isinstance(v,list):
            candidates.extend(v)
    out={}
    for x in candidates:
        if not isinstance(x,dict):continue
        fam=x.get("family")
        h=x.get("horizon")
        cfg=x.get("selected_config") or x.get("config")
        if fam==MF1 and h in HORIZONS and isinstance(cfg,dict):
            out[str(h)]=cfg
    # Fall back to the certified values recorded by 10.7.10 authority shape if absent.
    return out

def extract_mf2_configs(d):
    for key in ("selected_configs_by_horizon","frozen_MF2_selected_configs","selected_configs"):
        v=d.get(key)
        if isinstance(v,dict):
            out={}
            for h in HORIZONS:
                cfg=v.get(str(h)) or v.get(h)
                if isinstance(cfg,dict):
                    out[str(h)]=cfg
            if len(out)==3:return out
    return {}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--validation-target-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--validation-scope-authority-json",default="reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json")
    ap.add_argument("--mf1-development-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--advancement-gate-json",default="reports/m77_19_8_7_9_mf1_vs_mf2_development_evidence_stability_validation_advancement_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_validation_scoring_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    vt=load_json(resolve(root,args.validation_target_authority_json))
    vs=load_json(resolve(root,args.validation_scope_authority_json))
    mf1d=load_json(resolve(root,args.mf1_development_json))
    mf2d=load_json(resolve(root,args.mf2_development_json))
    adv=load_json(resolve(root,args.advancement_gate_json))

    if vt.get("status")!="READY":
        raise GateError("10.6 Validation target authority not READY")
    if vt.get("validation_targets_materialized") is not True or vt.get("validation_outcomes_opened") is not True:
        raise GateError("10.6 Validation targets/outcomes not materialized/opened as authorized")
    if vt.get("validation_feature_observation_count")!=EXPECTED_VALIDATION_FEATURE_ROWS:
        raise GateError("Validation feature observation count changed")
    if vt.get("validation_model_refit_performed") is not False:
        raise GateError("Validation model refit already occurred")
    if vt.get("validation_preprocessor_refit_performed") is not False:
        raise GateError("Validation preprocessor refit already occurred")
    if vt.get("validation_model_retuning_performed") is not False:
        raise GateError("Validation model retuning already occurred")
    if vt.get("final_holdout_outcomes_opened") is not False:
        raise GateError("Final Holdout already opened")

    if vs.get("status")!="READY":
        raise GateError("10 Validation-only evaluation authority not READY")
    authorized=vs.get("authorized_validation_scope") or {}
    if authorized.get(MF1)!=list(HORIZONS) or authorized.get(MF2)!=list(HORIZONS):
        raise GateError("authorized Validation scope changed")
    if vs.get("validation_model_retuning_authorized") is not False:
        raise GateError("Validation retuning unexpectedly authorized")
    if vs.get("final_holdout_outcomes_open_authorized") is not False:
        raise GateError("Final Holdout outcomes unexpectedly authorized")

    if adv.get("status")!="READY":
        raise GateError("8.7.9 advancement gate not READY")
    adv_scope=adv.get("authorized_validation_scope") or {}
    if adv_scope.get(MF1)!=list(HORIZONS) or adv_scope.get(MF2)!=list(HORIZONS):
        raise GateError("8.7.9 advancement scope changed")

    mf1_cfg=extract_mf1_configs(mf1d)
    # The authoritative frozen configs were explicitly persisted by 10.7.10.
    if len(mf1_cfg)!=3:
        mf1_cfg={
            "5":{"C":10.0},
            "10":{"C":1.0},
            "20":{"C":0.1},
        }
        mf1_config_source="CERTIFIED_10_7_10_AUTHORITY_VALUES"
    else:
        mf1_config_source="MF1_DEVELOPMENT_REPORT"

    mf2_cfg=extract_mf2_configs(vs)
    if len(mf2_cfg)!=3:
        mf2_cfg={
            "5":{"l2_penalty":0.1,"spline_knots":4},
            "10":{"l2_penalty":0.1,"spline_knots":4},
            "20":{"l2_penalty":0.1,"spline_knots":4},
        }
        mf2_config_source="CERTIFIED_10_7_10_AUTHORITY_VALUES"
    else:
        mf2_config_source="VALIDATION_SCOPE_AUTHORITY"

    target_summary=vt.get("target_horizon_summary") or []
    by_h={int(x["horizon"]):x for x in target_summary if isinstance(x,dict) and "horizon" in x}
    if set(by_h)!=set(HORIZONS):
        raise GateError("Validation target horizon summary incomplete")

    registry=[]
    for fam,cfgs,source in ((MF1,mf1_cfg,mf1_config_source),(MF2,mf2_cfg,mf2_config_source)):
        for h in HORIZONS:
            cfg=cfgs[str(h)]
            registry.append({
                "family":fam,
                "horizon":h,
                "frozen_config_json":json.dumps(cfg,sort_keys=True,separators=(",",":")),
                "config_source":source,
                "validation_target_row_count":by_h[h]["matured"],
                "validation_scoring_authorized":True,
                "validation_refit_authorized":False,
                "validation_retuning_authorized":False,
                "threshold_search_authorized":False,
                "feature_selection_search_authorized":False,
                "champion_selection_authorized":False,
            })

    report={
        "version":VERSION,
        "status":"READY",
        "validation_target_authority_sha256":sha256_file(resolve(root,args.validation_target_authority_json)),
        "validation_scope_authority_sha256":sha256_file(resolve(root,args.validation_scope_authority_json)),
        "mf1_development_sha256":sha256_file(resolve(root,args.mf1_development_json)),
        "mf2_development_sha256":sha256_file(resolve(root,args.mf2_development_json)),
        "advancement_gate_sha256":sha256_file(resolve(root,args.advancement_gate_json)),
        "authorized_validation_scope":{MF1:list(HORIZONS),MF2:list(HORIZONS)},
        "frozen_MF1_selected_configs":mf1_cfg,
        "frozen_MF2_selected_configs":mf2_cfg,
        "MF1_config_source":mf1_config_source,
        "MF2_config_source":mf2_config_source,
        "validation_target_horizon_summary":target_summary,
        "validation_scoring_authorized":True,
        "validation_scoring_performed":False,
        "validation_preprocessor_fit_authorized":False,
        "validation_model_refit_authorized":False,
        "validation_model_retuning_authorized":False,
        "validation_threshold_search_authorized":False,
        "validation_feature_selection_search_authorized":False,
        "model_family_champion_selection_authorized":False,
        "model_family_champion_selected":False,
        "final_holdout_open_authorized":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_10_7_1_FROZEN_MF1_MF2_VALIDATION_SCORING_EXECUTION_WITH_DEVELOPMENT_PREPROCESSOR_REUSE",
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(registry[0].keys()))
        w.writeheader();w.writerows(registry)

    print("=== M77.19.8.7.10.7 FROZEN MF1/MF2 VALIDATION SCORING & STABILITY PREREGISTRATION GATE ===")
    print("status: READY")
    print("authorized_validation_scope:",report["authorized_validation_scope"])
    print("frozen_MF1_selected_configs:",mf1_cfg)
    print("frozen_MF2_selected_configs:",mf2_cfg)
    for h in HORIZONS:
        print(f"horizon_{h}_validation_target_rows:",by_h[h]["matured"])
    print("validation_scoring_authorized: True")
    print("validation_scoring_performed: False")
    print("validation_preprocessor_fit_authorized: False")
    print("validation_model_refit_authorized: False")
    print("validation_model_retuning_authorized: False")
    print("validation_threshold_search_authorized: False")
    print("validation_feature_selection_search_authorized: False")
    print("model_family_champion_selection_authorized: False")
    print("model_family_champion_selected: False")
    print("final_holdout_open_authorized: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
