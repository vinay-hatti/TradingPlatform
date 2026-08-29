#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,os,sys,tempfile
from pathlib import Path

VERSION="M77.19.8.7.4-MF2-RUNTIME-MF3-ELASTIC-NET-QUANTILE-SOLVER-CERTIFICATION-1.0"
EXPECTED_873_VERSION="M77.19.8.7.3-MF2-MONOTONIC-SIGN-SEMANTIC-AUTHORITY-MF3-SOLVER-DECISION-GATE-1.0"

class CertError(RuntimeError):pass
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
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
    ap.add_argument("--semantic-gate-json",default="reports/m77_19_8_7_3_mf2_monotonic_sign_semantic_authority_mf3_solver_decision_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_4_mf2_runtime_mf3_elastic_net_quantile_solver_certification.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_4_solver_certification_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    sp=resolve(root,a.semantic_gate_json);sg=load_json(sp)
    if sg.get("version")!=EXPECTED_873_VERSION or sg.get("status")!="READY":raise CertError("M77.19.8.7.3 gate invalid")
    if sg.get("validation_open_authorized") is not False or sg.get("final_holdout_open_authorized") is not False:
        raise CertError("Validation/Final Holdout gate invalid")
    if importlib.util.find_spec("scipy") is None or importlib.util.find_spec("numpy") is None:
        raise CertError("numpy/scipy runtime required")

    from trading_ai.research.m77.m77_19_8_7_4_certified_solvers import synthetic_mf2_certification,synthetic_mf3_certification
    mf2_checks=synthetic_mf2_certification()
    mf3_checks=synthetic_mf3_certification()
    mf2_cert=all(mf2_checks.values())
    mf3_cert=bool(mf3_checks["all_finite"] and mf3_checks["all_objective_matches_contract"] and mf3_checks["median_fit_directionally_sane"])
    if not mf2_cert:raise CertError(f"MF2 synthetic certification failed: {mf2_checks}")
    if not mf3_cert:raise CertError(f"MF3 synthetic certification failed: {mf3_checks}")

    solver_path=root/"src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py"
    rows=[
      {"family":"MF2_MONOTONIC_GAM_DIRECTION","runtime":"SCIPY_LBFGSB_LINEAR_SPLINE_GAM","certified":True,"development_scoring_authorized":True},
      {"family":"MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION","runtime":"SCIPY_POWELL_EXACT_PINBALL_ELASTIC_NET_REFERENCE_SOLVER","certified":True,"development_scoring_authorized":False},
    ]
    report={
      "version":VERSION,"status":"READY","semantic_gate_sha256":sha256_file(sp),"solver_module_sha256":sha256_file(solver_path),
      "MF2":{
        "runtime":"SCIPY_LBFGSB_LINEAR_SPLINE_GAM",
        "objective":"LOGISTIC_NLL_PLUS_L2",
        "monotonic_enforcement":"COEFFICIENT_BOUNDS_ON_LINEAR_HINGE_SPLINE_BASIS",
        "semantic_sign_authority_required":True,
        "synthetic_certification":mf2_checks,
        "runtime_certified":True,
        "development_scoring_authorized":True,
      },
      "MF3":{
        "runtime":"SCIPY_POWELL_EXACT_PINBALL_ELASTIC_NET_REFERENCE_SOLVER",
        "objective":"MEAN_PINBALL_PLUS_ALPHA_TIMES_ELASTIC_NET",
        "alpha_supported":True,"l1_ratio_supported":True,"quantile_supported":True,
        "synthetic_certification":mf3_checks,
        "objective_contract_certified":True,
        "reference_runtime_certified":True,
        "development_scoring_authorized":False,
        "development_scoring_block_reason":"REFERENCE_SOLVER_EXACT_BUT_NOT_CERTIFIED_SCALABLE_FOR_300K_ROW_WALK_FORWARD",
        "next_requirement":"CERTIFY_SCALABLE_SOLVER_WITH_NUMERICAL_PARITY_TO_REFERENCE",
      },
      "model_family_comparison_complete":False,
      "validation_open_authorized":False,
      "final_holdout_open_authorized":False,
      "MF1_retuning_authorized":False,
      "preregistration_change_authorized":False,
      "production_authority_effect":False,
      "next_step":"BUILD_M77_19_8_7_5_MF2_DEVELOPMENT_WALK_FORWARD_AND_MF3_SCALABLE_SOLVER_PARITY_AUTHORITY",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print("=== M77.19.8.7.4 MF2 RUNTIME & MF3 ELASTIC-NET QUANTILE SOLVER CERTIFICATION ===")
    print("status: READY")
    print("MF2_runtime: SCIPY_LBFGSB_LINEAR_SPLINE_GAM")
    print("MF2_runtime_certified:",mf2_cert)
    print("MF2_development_scoring_authorized: True")
    print("MF3_runtime: SCIPY_POWELL_EXACT_PINBALL_ELASTIC_NET_REFERENCE_SOLVER")
    print("MF3_objective_contract_certified:",mf3_cert)
    print("MF3_reference_runtime_certified: True")
    print("MF3_development_scoring_authorized: False")
    print("MF3_block_reason: REFERENCE_SOLVER_EXACT_BUT_NOT_CERTIFIED_SCALABLE_FOR_300K_ROW_WALK_FORWARD")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("MF1_retuning_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_5_MF2_DEVELOPMENT_WALK_FORWARD_AND_MF3_SCALABLE_SOLVER_PARITY_AUTHORITY")
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
