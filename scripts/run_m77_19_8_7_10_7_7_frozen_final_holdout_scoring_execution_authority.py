#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
SCOPE={MF1:[5,10,20],MF2:[5,10,20]}
MF1_CFG={"5":{"C":10.0},"10":{"C":1.0},"20":{"C":0.1}}
MF2_CFG={"5":{"l2_penalty":0.1,"spline_knots":4},"10":{"l2_penalty":0.1,"spline_knots":4},"20":{"l2_penalty":0.1,"spline_knots":4}}
class AuthorityError(RuntimeError): pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
    ap.add_argument("--combined-invocation-json",default="reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json")
    ap.add_argument("--final-holdout-feature-json",default="reports/m77_19_8_7_10_7_6_1_final_holdout_context_feature_matrix_materialization.json")
    ap.add_argument("--final-holdout-target-json",default="reports/m77_19_8_7_10_7_6_2_1_final_holdout_target_materialization_authority.json")
    ap.add_argument("--validation-scoring-json",default="reports/m77_19_8_7_10_7_3_6_memory_bound_isolated_frozen_validation_scoring.json")
    ap.add_argument("--mf1-development-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-runtime-module",default="src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_7_frozen_final_holdout_scoring_execution_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_7_final_holdout_scoring_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    pp=R(root,a.protocol_json);ip=R(root,a.combined_invocation_json);fp=R(root,a.final_holdout_feature_json);tp=R(root,a.final_holdout_target_json);vp=R(root,a.validation_scoring_json)
    for p in (pp,ip,fp,tp,vp):
        if not p.exists():raise AuthorityError(f"required authority missing: {p}")
    protocol,inv,feat,targ,val=map(J,(pp,ip,fp,tp,vp))

    if protocol.get("status")!="READY" or protocol.get("final_holdout_protocol_preregistered") is not True:raise AuthorityError("10.7.5 protocol invalid")
    p=(protocol.get("protocol") or {})
    if p.get("final_holdout_scope")!=SCOPE:raise AuthorityError("Final Holdout scope changed")
    if p.get("frozen_MF1_selected_configs")!=MF1_CFG or p.get("frozen_MF2_selected_configs")!=MF2_CFG:raise AuthorityError("frozen configs changed")
    if p.get("fit_partition")!="DEVELOPMENT_ONLY" or p.get("preprocessor_fit_partition")!="DEVELOPMENT_ONLY":raise AuthorityError("fit partition changed")
    if p.get("decision_threshold")!=0.5 or p.get("primary_metric")!="BALANCED_ACCURACY":raise AuthorityError("metric/threshold contract changed")
    if p.get("multiclass_policy")!="DROP_ZERO_LABEL_ROWS_THEN_BINARY_UP_VS_DOWN":raise AuthorityError("target policy changed")
    if p.get("final_holdout_single_use_evaluation") is not True or p.get("final_holdout_role")!="PURE_FROZEN_EVIDENCE_ESTIMATION":raise AuthorityError("single-use holdout contract changed")
    for k in ("validation_fit_authorized","final_holdout_fit_authorized","threshold_search_authorized","feature_selection_search_authorized","hyperparameter_search_authorized"):
        if p.get(k) is not False:raise AuthorityError(f"protocol relaxed: {k}")

    if inv.get("status")!="READY" or inv.get("combined_exact_invocation_authority_certified") is not True:raise AuthorityError("combined invocation authority invalid")
    if inv.get("authorized_validation_scope")!=SCOPE:raise AuthorityError("invocation scope changed")
    if inv.get("validation_scoring_execution_authorized") is not True:raise AuthorityError("exact invocation not authorized")
    if inv.get("model_family_champion_selection_authorized") is not False or inv.get("final_holdout_open_authorized") is not False:raise AuthorityError("old authority unexpectedly relaxed")

    if feat.get("status")!="READY" or feat.get("final_holdout_feature_matrix_materialized") is not True:raise AuthorityError("Final Holdout feature authority invalid")
    if feat.get("validation_final_holdout_schema_identical") is not True or feat.get("required_backfill_features_full_coverage") is not True:raise AuthorityError("Final Holdout feature certification incomplete")
    if targ.get("status")!="READY" or targ.get("final_holdout_targets_materialized") is not True:raise AuthorityError("Final Holdout target authority invalid")
    if targ.get("target_formula_reimplementation_performed") is not False or targ.get("right_edge_unmatured_targets_remain_unlabeled") is not True:raise AuthorityError("Final Holdout target semantics changed")
    if targ.get("final_holdout_scoring_authorized") is not False or targ.get("final_holdout_scoring_performed") is not False:raise AuthorityError("Final Holdout already scored/authorized")
    if targ.get("model_family_champion_selection_authorized") is not False or targ.get("production_authority_effect") is not False:raise AuthorityError("target authority governance relaxed")

    if val.get("status")!="READY" or val.get("execution_mode")!="ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS":raise AuthorityError("Validation scoring execution implementation not certified")
    if val.get("validation_model_retuning_performed") is not False or val.get("model_family_champion_selected") is not False:raise AuthorityError("Validation scoring governance changed")

    summaries={int(x["horizon"]):x for x in targ.get("target_horizon_summary") or []}
    rows=[]
    eligible={}
    for h in (5,10,20):
        if h not in summaries:raise AuthorityError(f"h{h}: holdout target summary missing")
        s=summaries[h];binary=int(s["UP"])+int(s["DOWN"]);matured=int(s["matured"])
        if binary+int(s["ZERO"])!=matured:raise AuthorityError(f"h{h}: target label accounting mismatch")
        eligible[h]=binary
        for fam in (MF1,MF2):
            cfg=(MF1_CFG if fam==MF1 else MF2_CFG)[str(h)]
            rows.append({"family":fam,"horizon":h,"frozen_config_json":json.dumps(cfg,sort_keys=True),
                         "final_holdout_matured_rows":matured,"final_holdout_binary_eligible_rows":binary,
                         "zero_rows_excluded":int(s["ZERO"]),"decision_threshold":0.5,
                         "primary_metric":"BALANCED_ACCURACY","fit_partition":"DEVELOPMENT_ONLY"})

    for pth in (R(root,a.mf1_development_script),R(root,a.mf2_development_script),R(root,a.mf2_runtime_module)):
        if not pth.exists():raise AuthorityError(f"implementation file missing: {pth}")

    report={
      "version":"M77.19.8.7.10.7.7-FROZEN-FINAL-HOLDOUT-SCORING-EXECUTION-AUTHORITY-1.0","status":"READY",
      "upstream_sha256":{"protocol":H(pp),"combined_invocation":H(ip),"final_holdout_feature":H(fp),"final_holdout_target":H(tp),"validation_scoring":H(vp)},
      "implementation_sha256":{"MF1_development_script":H(R(root,a.mf1_development_script)),
                               "MF2_development_script":H(R(root,a.mf2_development_script)),
                               "MF2_runtime_module":H(R(root,a.mf2_runtime_module))},
      "authorized_final_holdout_scope":SCOPE,"frozen_MF1_selected_configs":MF1_CFG,"frozen_MF2_selected_configs":MF2_CFG,
      "final_holdout_binary_eligible_rows":{str(k):v for k,v in eligible.items()},
      "evaluation_population_frozen_before_scoring":True,
      "zero_label_rows_excluded_per_preregistered_policy":True,
      "development_only_model_fit_required":True,"development_only_preprocessor_fit_required":True,
      "validation_rows_used_for_fit":False,"final_holdout_rows_used_for_fit":False,
      "decision_threshold":0.5,"threshold_search_authorized":False,"feature_selection_search_authorized":False,
      "hyperparameter_search_authorized":False,"family_elimination_authorized":False,
      "execution_mode":"ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS",
      "single_use_final_holdout_scoring_authorized":True,"final_holdout_scoring_execution_authorized":True,
      "final_holdout_scoring_performed":False,
      "automatic_pass_fail_rule_defined":False,"final_holdout_role":"PURE_FROZEN_EVIDENCE_ESTIMATION",
      "model_family_champion_selection_authorized":False,"model_family_champion_selected":False,
      "production_model_change_authorized":False,"production_authority_effect":False,
      "next_step":"RUN_M77_19_8_7_10_7_7_1_MEMORY_BOUND_ISOLATED_FROZEN_FINAL_HOLDOUT_SCORING"
    }
    R(root,a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    with R(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=list(rows[0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.7 FROZEN FINAL HOLDOUT SCORING EXECUTION AUTHORITY ===")
    print("status: READY");print("authorized_final_holdout_scope:",SCOPE)
    print("final_holdout_binary_eligible_rows:",{str(k):v for k,v in eligible.items()})
    print("evaluation_population_frozen_before_scoring: True")
    print("development_only_model_fit_required: True");print("validation_rows_used_for_fit: False");print("final_holdout_rows_used_for_fit: False")
    print("decision_threshold: 0.5");print("threshold_search_authorized: False");print("feature_selection_search_authorized: False");print("hyperparameter_search_authorized: False")
    print("execution_mode: ONE_FAMILY_HORIZON_PER_FRESH_SUBPROCESS")
    print("single_use_final_holdout_scoring_authorized: True");print("final_holdout_scoring_execution_authorized: True");print("final_holdout_scoring_performed: False")
    print("automatic_pass_fail_rule_defined: False");print("model_family_champion_selection_authorized: False");print("model_family_champion_selected: False")
    print("production_authority_effect: False");print("next_step:",report["next_step"]);print("report:",R(root,a.output_json));print("csv:",R(root,a.output_csv))
if __name__=="__main__":main()
