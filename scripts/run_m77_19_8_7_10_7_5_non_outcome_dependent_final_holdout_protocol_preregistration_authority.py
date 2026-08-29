#!/usr/bin/env python3
import argparse,csv,json,hashlib
from pathlib import Path

MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"; MF2="MF2_MONOTONIC_GAM_DIRECTION"
SCOPE={MF1:[5,10,20],MF2:[5,10,20]}
C1={"5":{"C":10.0},"10":{"C":1.0},"20":{"C":0.1}}
C2={"5":{"l2_penalty":0.1,"spline_knots":4},"10":{"l2_penalty":0.1,"spline_knots":4},"20":{"l2_penalty":0.1,"spline_knots":4}}
def J(p): return json.loads(Path(p).read_text())
def H(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def R(root,p): p=Path(p); return p if p.is_absolute() else root/p
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 ap.add_argument("--validation-governance-gate-json",default="reports/m77_19_8_7_10_7_4_validation_evidence_stability_final_holdout_advancement_gate.json")
 ap.add_argument("--validation-scope-json",default="reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json")
 ap.add_argument("--validation-preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
 ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
 ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
 ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_5_final_holdout_scope_registry.csv")
 a=ap.parse_args(); root=Path(a.project_root).resolve()
 gp,sp,pp,tp=[R(root,x) for x in (a.validation_governance_gate_json,a.validation_scope_json,a.validation_preregistration_json,a.training_gate_json)]
 g,s,p,t=map(J,(gp,sp,pp,tp))
 assert g["status"]=="BLOCKED_FINAL_HOLDOUT_ADVANCEMENT_CRITERIA_NOT_PREREGISTERED_BEFORE_VALIDATION"
 assert g["substantive_preexisting_final_holdout_advancement_rule_count"]==0
 assert all(g[x] is False for x in ("post_validation_threshold_definition_authorized","validation_used_for_family_selection","model_family_champion_selected","final_holdout_opened","production_authority_effect"))
 assert s["authorized_validation_scope"]==SCOPE==p["authorized_validation_scope"]
 assert s["frozen_MF1_selected_configs"]==C1==p["frozen_MF1_selected_configs"]
 assert s["frozen_MF2_selected_configs"]==C2==p["frozen_MF2_selected_configs"]
 assert t["selection_and_metrics"]["validation_used_for_selection"] is False
 assert t["selection_and_metrics"]["final_holdout_used_for_selection"] is False
 protocol={"scope_derivation":"IDENTICAL_TO_PREVALIDATION_AUTHORIZED_VALIDATION_SCOPE","final_holdout_scope":SCOPE,
 "frozen_MF1_selected_configs":C1,"frozen_MF2_selected_configs":C2,"target":"T_DIRECTION",
 "multiclass_policy":"DROP_ZERO_LABEL_ROWS_THEN_BINARY_UP_VS_DOWN","decision_threshold":0.5,
 "primary_metric":"BALANCED_ACCURACY","secondary_metrics":["LOG_LOSS","Brier_SCORE","ROC_AUC"],
 "fit_partition":"DEVELOPMENT_ONLY","preprocessor_fit_partition":"DEVELOPMENT_ONLY",
 "validation_fit_authorized":False,"final_holdout_fit_authorized":False,
 "validation_performance_used_to_choose_holdout_scope":False,"validation_performance_used_to_eliminate_family":False,
 "threshold_search_authorized":False,"feature_selection_search_authorized":False,"hyperparameter_search_authorized":False,
 "final_holdout_single_use_evaluation":True,"automatic_final_holdout_pass_fail_rule_defined":False,
 "final_holdout_role":"PURE_FROZEN_EVIDENCE_ESTIMATION"}
 out={"version":"M77.19.8.7.10.7.5-1.0","status":"READY","protocol":protocol,
 "upstream_sha256":{"10_7_4":H(gp),"10":H(sp),"10_7":H(pp),"8_6":H(tp)},
 "final_holdout_protocol_preregistered":True,"non_outcome_dependent_scope_certified":True,
 "post_validation_numeric_acceptance_threshold_defined":False,"model_family_champion_selection_authorized":False,
 "model_family_champion_selected":False,"MF1_retuning_authorized":False,"MF2_retuning_authorized":False,
 "final_holdout_feature_materialization_authorized":True,
 "final_holdout_target_materialization_authorized_after_exact_feature_certification":True,
 "final_holdout_scoring_authorized_by_this_step":False,"final_holdout_open_authorized":True,
 "final_holdout_opened":False,"production_authority_effect":False,
 "next_step":"BUILD_M77_19_8_7_10_7_6_FINAL_HOLDOUT_FEATURE_TARGET_MATERIALIZATION_AUTHORITY"}
 R(root,a.output_json).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 rows=[]
 for fam in SCOPE:
  for h in SCOPE[fam]: rows.append({"family":fam,"horizon":h,"config":json.dumps((C1 if fam==MF1 else C2)[str(h)],sort_keys=True)})
 with R(root,a.output_csv).open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=["family","horizon","config"]);w.writeheader();w.writerows(rows)
 print("=== M77.19.8.7.10.7.5 NON-OUTCOME-DEPENDENT FINAL HOLDOUT PROTOCOL ===")
 print("status: READY"); print("final_holdout_scope:",SCOPE)
 print("final_holdout_role: PURE_FROZEN_EVIDENCE_ESTIMATION")
 print("validation_performance_used_to_choose_holdout_scope: False")
 print("post_validation_numeric_acceptance_threshold_defined: False")
 print("final_holdout_single_use_evaluation: True")
 print("final_holdout_feature_materialization_authorized: True")
 print("final_holdout_scoring_authorized_by_this_step: False")
 print("model_family_champion_selected: False");print("final_holdout_open_authorized: True")
 print("final_holdout_opened: False");print("production_authority_effect: False")
 print("next_step:",out["next_step"]);print("report:",R(root,a.output_json));print("csv:",R(root,a.output_csv))
if __name__=="__main__": main()
