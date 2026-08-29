#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10-AUTHORIZED-MODEL-FAMILY-VALIDATION-ONLY-EVALUATION-AUTHORITY-1.0"
EXPECTED_879_VERSION="M77.19.8.7.9-MF1-VS-MF2-DEVELOPMENT-EVIDENCE-STABILITY-VALIDATION-ADVANCEMENT-GATE-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"

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
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--advancement-gate-json",default="reports/m77_19_8_7_9_mf1_vs_mf2_development_evidence_stability_validation_advancement_gate.json")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--development-matrix-authority-json",default="reports/m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_validation_scope_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    gp=resolve(root,a.advancement_gate_json)
    fp=resolve(root,a.feature_authority_json)
    dp=resolve(root,a.development_matrix_authority_json)
    tp=resolve(root,a.training_gate_json)
    for p in (gp,fp,dp,tp):
        if not p.exists():raise AuthorityError(f"missing upstream authority: {p}")
    gate=load_json(gp)
    if gate.get("version")!=EXPECTED_879_VERSION or gate.get("status")!="READY":
        raise AuthorityError("M77.19.8.7.9 authority invalid")
    if gate.get("validation_outcomes_read") is not False or gate.get("validation_scoring_performed") is not False:
        raise AuthorityError("8.7.9 must not have opened Validation outcomes")
    if gate.get("final_holdout_open_authorized") is not False:
        raise AuthorityError("Final Holdout governance violated")

    scope=gate.get("authorized_validation_scope") or {}
    expected={
        "MF1_REGULARIZED_LOGISTIC_DIRECTION":[5,10,20],
        "MF2_MONOTONIC_GAM_DIRECTION":[5,10,20],
    }
    if scope!=expected:
        raise AuthorityError(f"authorized validation scope changed: {scope}")

    mf1={}
    mf2={}
    for rec in gate.get("family_horizon_evidence") or []:
        fam=rec.get("family");h=int(rec.get("horizon"))
        if not rec.get("development_advancement_pass"):
            raise AuthorityError(f"authorized cell lacks Development pass: {fam} h{h}")
        if fam=="MF1_REGULARIZED_LOGISTIC_DIRECTION":mf1[str(h)]=rec.get("selected_config")
        elif fam=="MF2_MONOTONIC_GAM_DIRECTION":mf2[str(h)]=rec.get("selected_config")

    if set(mf1)!=set(("5","10","20")) or set(mf2)!=set(("5","10","20")):
        raise AuthorityError("frozen selected configurations missing")

    # Exact Validation feature authority does not yet exist in the governed chain.
    # Development feature materialization was explicitly Development-only.
    development=load_json(dp)
    validation_matrix_already_materialized=bool(
        development.get("validation_feature_rows_materialized") or
        development.get("validation_matrix_materialized")
    )
    if validation_matrix_already_materialized:
        raise AuthorityError("unexpected Validation feature materialization detected upstream")

    rows=[]
    for fam,configs in (("MF1_REGULARIZED_LOGISTIC_DIRECTION",mf1),
                        ("MF2_MONOTONIC_GAM_DIRECTION",mf2)):
        for h in (5,10,20):
            rows.append({
                "family":fam,"horizon":h,"selected_config_json":json.dumps(configs[str(h)],sort_keys=True),
                "validation_authorized":True,"retuning_authorized":False,
            })

    report={
        "version":VERSION,"status":"READY",
        "advancement_gate_sha256":sha256_file(gp),
        "feature_authority_sha256":sha256_file(fp),
        "development_matrix_authority_sha256":sha256_file(dp),
        "training_gate_sha256":sha256_file(tp),
        "validation_window":{"start":VALIDATION_START,"end":VALIDATION_END},
        "authorized_validation_scope":scope,
        "frozen_MF1_selected_configs":mf1,
        "frozen_MF2_selected_configs":mf2,
        "validation_feature_matrix_authority_exists":False,
        "validation_feature_materialization_authorized":True,
        "validation_feature_materialization_must_reuse_exact_frozen_PIT_extractors":True,
        "validation_feature_approximation_authorized":False,
        "validation_feature_refitting_authorized":False,
        "validation_preprocessor_fit_on_validation_authorized":False,
        "validation_model_retuning_authorized":False,
        "validation_outcomes_open_authorized_after_exact_feature_materialization":True,
        "validation_scoring_performed_by_this_step":False,
        "final_holdout_context_open_authorized":False,
        "final_holdout_outcomes_open_authorized":False,
        "MF3_reopened":False,
        "model_family_champion_selected":False,
        "production_model_change_authorized":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_10_1_EXACT_PIT_VALIDATION_FEATURE_MATRIX_MATERIALIZATION_AND_FROZEN_PREPROCESSOR_AUTHORITY",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10 AUTHORIZED MODEL-FAMILY VALIDATION-ONLY EVALUATION AUTHORITY ===")
    print("status: READY")
    print("validation_window: 2018-01-01 .. 2022-12-31")
    print("authorized_validation_scope:",scope)
    print("frozen_MF1_selected_configs:",mf1)
    print("frozen_MF2_selected_configs:",mf2)
    print("validation_feature_matrix_authority_exists: False")
    print("validation_feature_materialization_authorized: True")
    print("validation_feature_approximation_authorized: False")
    print("validation_model_retuning_authorized: False")
    print("validation_scoring_performed_by_this_step: False")
    print("final_holdout_context_open_authorized: False")
    print("final_holdout_outcomes_open_authorized: False")
    print("MF3_reopened: False")
    print("model_family_champion_selected: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_10_1_EXACT_PIT_VALIDATION_FEATURE_MATRIX_MATERIALIZATION_AND_FROZEN_PREPROCESSOR_AUTHORITY")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
