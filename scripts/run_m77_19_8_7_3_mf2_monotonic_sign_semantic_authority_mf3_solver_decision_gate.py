#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,os,re,tempfile
from pathlib import Path

VERSION="M77.19.8.7.3-MF2-MONOTONIC-SIGN-SEMANTIC-AUTHORITY-MF3-SOLVER-DECISION-GATE-1.0"
EXPECTED_872_VERSION="M77.19.8.7.2-MF2-MF3-IMPLEMENTATION-AUTHORITY-1.0"
EXPECTED_86_VERSION="M77.19.8.6-STRUCTURED-FEATURE-MATERIALIZATION-DEVELOPMENT-MODEL-TRAINING-PREREGISTRATION-GATE-1.0"

# Conservative ex-ante semantic rules. They operate on feature identity/path only.
# They never inspect outcomes, target statistics, MF1 coefficients, or Validation.
EXACT_SIGN_RULES={
    "F070__rs_13w": 1,
    "F070__rs_26w": 1,
    "F080": 1,   # drawdown-from-52w-peak: larger/less negative = stronger price state
}
POSITIVE_TOKENS={
    "bullish","uptrend","positive","strength","alignment","momentum","accumulation",
    "breakout","participation","buying","demand","support_strength","relative_strength",
}
NEGATIVE_TOKENS={
    "bearish","downtrend","negative","distribution","capitulation","breakdown",
    "selling","supply","drawdown_depth",
}
AMBIGUOUS_TOKENS={
    "volatility","atr","range","distance","resistance","support","volume","confidence",
    "score","state","close","price","freshness","persistence","transition",
}

class GateError(RuntimeError): pass

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

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def tokens(s):
    return {x for x in re.split(r"[^a-zA-Z0-9]+",str(s).lower()) if x}

def semantic_sign(column_name,source_path=None):
    if column_name in EXACT_SIGN_RULES:
        return EXACT_SIGN_RULES[column_name],"EXACT_EX_ANTE_RULE"
    joined=f"{column_name} {source_path or ''}".lower()
    ts=tokens(joined)
    if ts & AMBIGUOUS_TOKENS:
        return 0,"UNCONSTRAINED_AMBIGUOUS_SEMANTICS"
    pos=bool(ts & POSITIVE_TOKENS);neg=bool(ts & NEGATIVE_TOKENS)
    if pos and not neg:return 1,"TOKEN_EX_ANTE_POSITIVE"
    if neg and not pos:return -1,"TOKEN_EX_ANTE_NEGATIVE"
    return 0,"UNCONSTRAINED_NO_DEFENSIBLE_SIGN"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--implementation-authority-json",default="reports/m77_19_8_7_2_mf2_mf3_implementation_authority.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_3_mf2_monotonic_sign_semantic_authority_mf3_solver_decision_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_3_mf2_monotonic_sign_registry.csv")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()
    ip=resolve(root,a.implementation_authority_json);gp=resolve(root,a.training_gate_json)
    ia=load_json(ip);gate=load_json(gp)
    if ia.get("version")!=EXPECTED_872_VERSION or ia.get("status")!="READY":raise GateError("M77.19.8.7.2 authority invalid")
    if gate.get("version")!=EXPECTED_86_VERSION or gate.get("status")!="READY":raise GateError("M77.19.8.6 gate invalid")
    if ia.get("validation_open_authorized") is not False or ia.get("final_holdout_open_authorized") is not False:
        raise GateError("Validation/Final Holdout must remain sealed")

    # Build the frozen MF2 sign registry from the 8.6 feature contract.
    registry=[]
    constrained=0
    # Base feature IDs from 8.6. Only exact known semantics are constrained.
    base_ids=(gate.get("training_feature_contract") or {}).get("existing_base_feature_ids") or []
    base_cols=[]
    for fid in base_ids:
        if fid=="F071":continue
        base_cols.append((fid,None))
    # F070 expands to two exact scalar columns in 8.7.
    base_cols=[x for x in base_cols if x[0]!="F070"]+[("F070__rs_13w",None),("F070__rs_26w",None)]

    structured=[(x["column_name"],x.get("source_path")) for x in gate.get("structured_columns") or []]
    seen=set()
    for col,path in base_cols+structured:
        if col in seen:continue
        seen.add(col)
        sign,reason=semantic_sign(col,path)
        if sign:constrained+=1
        registry.append({
            "column_name":col,"source_path":path or "",
            "monotonic_sign":sign,
            "sign_meaning":"NONDECREASING_UP_PROBABILITY" if sign==1 else "NONINCREASING_UP_PROBABILITY" if sign==-1 else "UNCONSTRAINED",
            "authority_reason":reason,
            "outcomes_used":False,
        })

    if constrained<2:
        raise GateError("MF2 semantic authority produced too few defensible constrained features")

    pygam_available=importlib.util.find_spec("pygam") is not None
    mf2={
        "field_level_monotonic_sign_map_materialized":True,
        "registered_column_count":len(registry),
        "constrained_column_count":constrained,
        "unconstrained_column_count":len(registry)-constrained,
        "outcomes_used_to_choose_signs":False,
        "MF1_coefficients_used_to_choose_signs":False,
        "validation_used_to_choose_signs":False,
        "pygam_runtime_available":pygam_available,
        "semantic_authority_certified":True,
        "runtime_certified":False,
        "development_scoring_authorized":False,
        "next_requirement":"CERTIFY_MONOTONIC_GAM_RUNTIME_IMPLEMENTATION",
    }

    # MF3 solver feasibility census. A solver must support the exact convex objective:
    # pinball loss + alpha * (l1_ratio*||beta||_1 + (1-l1_ratio)/2*||beta||_2^2)
    # across all preregistered quantiles. Existing sklearn QuantileRegressor is insufficient.
    runtime={
        "cvxpy":importlib.util.find_spec("cvxpy") is not None,
        "scipy":importlib.util.find_spec("scipy") is not None,
        "sklearn":importlib.util.find_spec("sklearn") is not None,
    }
    mf3_grid=((gate.get("model_family_preregistration") or {}).get("MF3_QUANTILE_LINEAR_RETURN_DISTRIBUTION") or {}).get("fixed_grid") or {}
    mf3={
        "required_objective":"PINBALL_PLUS_ELASTIC_NET",
        "required_alpha_grid":mf3_grid.get("alpha"),
        "required_l1_ratio_grid":mf3_grid.get("l1_ratio"),
        "sklearn_quantile_regressor_certified":False,
        "runtime_census":runtime,
        "custom_or_cvxpy_solver_implementation_authorized":True,
        "preregistration_rewrite_authorized":False,
        "family_retirement_authorized_at_this_gate":False,
        "development_scoring_authorized":False,
        "decision":"IMPLEMENT_CERTIFIED_SOLVER_IF_RUNTIME_FEASIBLE_ELSE_FORMAL_RETIREMENT_GATE",
    }

    report={
        "version":VERSION,"status":"READY",
        "implementation_authority_sha256":sha256_file(ip),"training_gate_sha256":sha256_file(gp),
        "MF2":mf2,"MF3":mf3,
        "model_family_comparison_complete":False,
        "validation_open_authorized":False,
        "final_holdout_open_authorized":False,
        "MF1_retuning_authorized":False,
        "outcome_driven_sign_revision_authorized":False,
        "preregistration_change_authorized":False,
        "production_model_change_authorized":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_4_MF2_RUNTIME_AND_MF3_ELASTIC_NET_QUANTILE_SOLVER_CERTIFICATION",
    }

    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(registry[0].keys()));w.writeheader();w.writerows(registry)

    print("=== M77.19.8.7.3 MF2 MONOTONIC SIGN SEMANTIC AUTHORITY & MF3 SOLVER DECISION GATE ===")
    print("status: READY")
    print("MF2_registered_column_count:",len(registry))
    print("MF2_constrained_column_count:",constrained)
    print("MF2_unconstrained_column_count:",len(registry)-constrained)
    print("MF2_outcomes_used_to_choose_signs: False")
    print("MF2_pygam_runtime_available:",pygam_available)
    print("MF2_semantic_authority_certified: True")
    print("MF2_runtime_certified: False")
    print("MF2_development_scoring_authorized: False")
    print("MF3_runtime_census:",runtime)
    print("MF3_required_objective: PINBALL_PLUS_ELASTIC_NET")
    print("MF3_custom_or_cvxpy_solver_implementation_authorized: True")
    print("MF3_preregistration_rewrite_authorized: False")
    print("MF3_development_scoring_authorized: False")
    print("model_family_comparison_complete: False")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("MF1_retuning_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_4_MF2_RUNTIME_AND_MF3_ELASTIC_NET_QUANTILE_SOLVER_CERTIFICATION")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
