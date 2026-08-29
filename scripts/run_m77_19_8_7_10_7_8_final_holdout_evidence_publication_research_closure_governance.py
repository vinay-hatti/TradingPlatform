#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
from statistics import fmean,pstdev

MF1="MF1_REGULARIZED_LOGISTIC_DIRECTION"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
FAMILIES=(MF1,MF2);HORIZONS=(5,10,20)
class ClosureError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def index_metrics(report,label):
    rows=report.get("family_horizon_metrics") or []
    out={}
    for x in rows:
        fam=x.get("family");h=int(x.get("horizon"))
        if fam in FAMILIES and h in HORIZONS:
            k=(fam,h)
            if k in out:raise ClosureError(f"{label}: duplicate metric {k}")
            out[k]=x
    missing=[(f,h) for f in FAMILIES for h in HORIZONS if (f,h) not in out]
    if missing:raise ClosureError(f"{label}: missing family/horizon metrics {missing}")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
    ap.add_argument("--validation-scoring-json",default="reports/m77_19_8_7_10_7_3_6_memory_bound_isolated_frozen_validation_scoring.json")
    ap.add_argument("--validation-advancement-json",default="reports/m77_19_8_7_10_7_4_validation_evidence_stability_final_holdout_advancement_gate.json")
    ap.add_argument("--final-holdout-feature-json",default="reports/m77_19_8_7_10_7_6_1_final_holdout_context_feature_matrix_materialization.json")
    ap.add_argument("--final-holdout-target-json",default="reports/m77_19_8_7_10_7_6_2_1_final_holdout_target_materialization_authority.json")
    ap.add_argument("--final-holdout-scoring-authority-json",default="reports/m77_19_8_7_10_7_7_frozen_final_holdout_scoring_execution_authority.json")
    ap.add_argument("--final-holdout-scoring-json",default="reports/m77_19_8_7_10_7_7_1_memory_bound_isolated_frozen_final_holdout_scoring.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_8_final_holdout_evidence_publication_research_closure_governance.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_8_development_validation_final_holdout_evidence_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    paths=[R(root,x) for x in (a.protocol_json,a.validation_scoring_json,a.validation_advancement_json,a.final_holdout_feature_json,a.final_holdout_target_json,a.final_holdout_scoring_authority_json,a.final_holdout_scoring_json)]
    for p in paths:
        if not p.exists():raise ClosureError(f"required authority missing: {p}")
    protocol,val,vadv,feat,targ,sa,final=map(J,paths)

    if protocol.get("status")!="READY" or protocol.get("final_holdout_protocol_preregistered") is not True:raise ClosureError("10.7.5 protocol invalid")
    pp=protocol.get("protocol") or {}
    if pp.get("final_holdout_role")!="PURE_FROZEN_EVIDENCE_ESTIMATION" or pp.get("final_holdout_single_use_evaluation") is not True:raise ClosureError("Final Holdout role changed")
    if pp.get("automatic_final_holdout_pass_fail_rule_defined") is not False:raise ClosureError("unexpected predeclared automatic pass/fail rule")
    if val.get("status")!="READY" or val.get("validation_scoring_performed") is not True:raise ClosureError("Validation scoring invalid")
    if val.get("validation_model_retuning_performed") is not False or val.get("model_family_champion_selected") is not False:raise ClosureError("Validation governance violated")
    if vadv.get("status")!="BLOCKED_FINAL_HOLDOUT_ADVANCEMENT_CRITERIA_NOT_PREREGISTERED_BEFORE_VALIDATION":raise ClosureError("10.7.4 historical governance state changed")
    if vadv.get("post_validation_threshold_definition_authorized") is not False or vadv.get("model_family_champion_selected") is not False:raise ClosureError("10.7.4 posthoc governance relaxed")
    if feat.get("status")!="READY" or feat.get("final_holdout_feature_matrix_materialized") is not True:raise ClosureError("Final Holdout feature authority invalid")
    if targ.get("status")!="READY" or targ.get("final_holdout_targets_materialized") is not True:raise ClosureError("Final Holdout target authority invalid")
    if sa.get("status")!="READY" or sa.get("evaluation_population_frozen_before_scoring") is not True:raise ClosureError("Final Holdout scoring authority invalid")
    if sa.get("automatic_pass_fail_rule_defined") is not False or sa.get("model_family_champion_selection_authorized") is not False:raise ClosureError("Final Holdout scoring authority governance relaxed")
    if final.get("status")!="READY" or final.get("final_holdout_scoring_performed") is not True or final.get("single_use_final_holdout_scoring_consumed") is not True:raise ClosureError("Final Holdout scoring incomplete")
    for k in ("final_holdout_model_refit_performed","final_holdout_preprocessor_refit_performed","final_holdout_model_retuning_performed","threshold_search_performed","feature_selection_search_performed","hyperparameter_search_performed","automatic_pass_fail_rule_applied","model_family_champion_selected","production_authority_effect"):
        if final.get(k) is not False:raise ClosureError(f"Final Holdout governance violated: {k}")

    vm=index_metrics(val,"Validation");fm=index_metrics(final,"Final Holdout")
    registry=[];summary={}
    for fam in FAMILIES:
        vba=[];fba=[];vauc=[];fauc=[]
        for h in HORIZONS:
            v=vm[(fam,h)];f=fm[(fam,h)]
            row={"family":fam,"horizon":h,
                 "validation_balanced_accuracy":float(v["balanced_accuracy"]),
                 "final_holdout_balanced_accuracy":float(f["balanced_accuracy"]),
                 "balanced_accuracy_delta_final_minus_validation":float(f["balanced_accuracy"])-float(v["balanced_accuracy"]),
                 "validation_log_loss":v.get("log_loss"),"final_holdout_log_loss":f.get("log_loss"),
                 "validation_brier_score":v.get("brier_score"),"final_holdout_brier_score":f.get("brier_score"),
                 "validation_roc_auc":v.get("roc_auc"),"final_holdout_roc_auc":f.get("roc_auc"),
                 "final_holdout_binary_rows":int(f["final_holdout_binary_rows"])}
            registry.append(row);vba.append(row["validation_balanced_accuracy"]);fba.append(row["final_holdout_balanced_accuracy"])
            if row["validation_roc_auc"] is not None:vauc.append(float(row["validation_roc_auc"]))
            if row["final_holdout_roc_auc"] is not None:fauc.append(float(row["final_holdout_roc_auc"]))
        summary[fam]={"validation_mean_balanced_accuracy":fmean(vba),"final_holdout_mean_balanced_accuracy":fmean(fba),
                      "mean_balanced_accuracy_delta_final_minus_validation":fmean(fba)-fmean(vba),
                      "validation_std_balanced_accuracy":pstdev(vba),"final_holdout_std_balanced_accuracy":pstdev(fba),
                      "final_holdout_above_chance_horizons":sum(x>0.5 for x in fba),"horizon_count":3,
                      "validation_mean_roc_auc":None if not vauc else fmean(vauc),"final_holdout_mean_roc_auc":None if not fauc else fmean(fauc)}

    descriptive_higher=max(FAMILIES,key=lambda f:summary[f]["final_holdout_mean_balanced_accuracy"])
    report={"version":"M77.19.8.7.10.7.8-FINAL-HOLDOUT-EVIDENCE-PUBLICATION-RESEARCH-CLOSURE-GOVERNANCE-1.0","status":"READY",
      "upstream_sha256":{"protocol":H(paths[0]),"validation_scoring":H(paths[1]),"validation_advancement":H(paths[2]),"final_holdout_feature":H(paths[3]),"final_holdout_target":H(paths[4]),"final_holdout_scoring_authority":H(paths[5]),"final_holdout_scoring":H(paths[6])},
      "evidence_summary":summary,"family_horizon_evidence":registry,
      "descriptive_higher_final_holdout_mean_balanced_accuracy_family":descriptive_higher,
      "descriptive_ordering_is_not_champion_selection":True,
      "final_holdout_evidence_interpretation":"PUBLISHED_DESCRIPTIVE_EVIDENCE_ONLY_NO_POSTHOC_ACCEPTANCE_THRESHOLD",
      "automatic_pass_fail_rule_defined":False,"automatic_pass_fail_rule_applied":False,
      "post_final_holdout_threshold_definition_authorized":False,
      "final_holdout_reuse_for_retuning_authorized":False,"final_holdout_reuse_for_feature_selection_authorized":False,
      "final_holdout_reuse_for_hyperparameter_search_authorized":False,"final_holdout_reuse_for_family_selection_authorized":False,
      "additional_model_family_comparison_using_this_holdout_authorized":False,
      "new_preregistration_required_for_future_model_research":True,
      "model_family_champion_selection_authorized":False,"model_family_champion_selected":False,
      "production_model_change_authorized":False,"production_promotion_performed":False,"production_authority_effect":False,
      "research_branch_state":"CLOSED_EVIDENCE_PUBLISHED_NO_PRODUCTION_PROMOTION",
      "research_branch_closed":True,
      "next_step":"RETURN_TO_M77_ROADMAP_WITH_NEW_PREREGISTRATION_REQUIRED_FOR_ANY_FUTURE_MODEL_OR_FEATURE_RESEARCH"}
    R(root,a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    with R(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=list(registry[0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(registry)

    print("=== M77.19.8.7.10.7.8 FINAL HOLDOUT EVIDENCE PUBLICATION & RESEARCH CLOSURE GOVERNANCE ===")
    print("status: READY")
    for fam in FAMILIES:
        s=summary[fam]
        print(f"{fam}: validation_mean_bal_acc={s['validation_mean_balanced_accuracy']:.9f} final_holdout_mean_bal_acc={s['final_holdout_mean_balanced_accuracy']:.9f} delta={s['mean_balanced_accuracy_delta_final_minus_validation']:.9f} final_above_chance={s['final_holdout_above_chance_horizons']}/3")
    print("descriptive_higher_final_holdout_mean_balanced_accuracy_family:",descriptive_higher)
    print("descriptive_ordering_is_not_champion_selection: True")
    print("automatic_pass_fail_rule_defined: False");print("post_final_holdout_threshold_definition_authorized: False")
    print("final_holdout_reuse_for_retuning_authorized: False");print("final_holdout_reuse_for_family_selection_authorized: False")
    print("new_preregistration_required_for_future_model_research: True")
    print("model_family_champion_selected: False");print("production_promotion_performed: False");print("production_authority_effect: False")
    print("research_branch_state: CLOSED_EVIDENCE_PUBLISHED_NO_PRODUCTION_PROMOTION");print("research_branch_closed: True")
    print("next_step:",report["next_step"]);print("report:",R(root,a.output_json));print("csv:",R(root,a.output_csv))
if __name__=="__main__":main()
