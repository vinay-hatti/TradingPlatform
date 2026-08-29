#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

VERSION="M77.20.0-PROSPECTIVE-EDGE-CYCLE2-PREREGISTRATION-CONSUMED-HOLDOUT-LOCK-AUTHORITY-1.0"
F071="F071"
HORIZONS=[5,10,20]
PROSPECTIVE_START="2026-08-24"
CONSUMED_HOLDOUT_END="2026-08-21"

class AuthorityError(RuntimeError):pass
def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def need_false(o,k,label):
    if o.get(k) is not False:raise AuthorityError(f"{label}: expected {k}=False")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--closure-json",default="reports/m77_19_8_7_10_7_8_final_holdout_evidence_publication_research_closure_governance.json")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--extractor-authority-json",default="reports/m77_19_8_3_blocked_feature_extractor_authority_development_target_matrix_preregistration.json")
    ap.add_argument("--structured-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--historical-analytics-source",default="src/trading_ai/historical_underlying_replay/analytics.py")
    ap.add_argument("--trend-service-source",default="src/trading_ai/trend_intelligence/service.py")
    ap.add_argument("--output-json",default="reports/m77_20_0_prospective_edge_cycle2_preregistration_consumed_holdout_lock_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_20_0_cycle2_research_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cp,fp,ep,sp,gp,hp,tp=[R(root,x) for x in (
        a.closure_json,a.feature_authority_json,a.extractor_authority_json,
        a.structured_target_authority_json,a.training_gate_json,
        a.historical_analytics_source,a.trend_service_source)]
    for p in (cp,fp,ep,sp,gp,hp,tp):
        if not p.exists():raise AuthorityError(f"required source missing: {p}")

    closure,feature,extractor,structured,gate=map(J,(cp,fp,ep,sp,gp))
    if closure.get("status")!="READY" or closure.get("research_branch_closed") is not True:raise AuthorityError("M77.19 closure invalid")
    if closure.get("research_branch_state")!="CLOSED_EVIDENCE_PUBLISHED_NO_PRODUCTION_PROMOTION":raise AuthorityError("M77.19 closure state changed")
    if closure.get("new_preregistration_required_for_future_model_research") is not True:raise AuthorityError("new preregistration requirement missing")
    for k in ("final_holdout_reuse_for_retuning_authorized","final_holdout_reuse_for_feature_selection_authorized",
              "final_holdout_reuse_for_hyperparameter_search_authorized","final_holdout_reuse_for_family_selection_authorized",
              "additional_model_family_comparison_using_this_holdout_authorized","model_family_champion_selected",
              "production_promotion_performed","production_authority_effect"):
        need_false(closure,k,"M77.19 closure")

    f=[x for x in feature.get("features") or [] if x.get("id")==F071]
    if feature.get("status")!="READY" or len(f)!=1:raise AuthorityError("F071 feature authority invalid")
    if f[0].get("source")!="PIT_SECTOR_BENCHMARK_REQUIRED" or f[0].get("transform")!="NOT_MATERIALIZED_UNTIL_SECTOR_PIT_AUTHORITY_EXISTS":raise AuthorityError("F071 source/transform changed")
    if (feature.get("materialization_contract") or {}).get("sector_relative_strength_blocked_until_pit_sector_authority") is not True:raise AuthorityError("F071 PIT guard missing")

    extractor_rows=extractor.get("extractors")
    if not isinstance(extractor_rows,list):
        raise AuthorityError("M77.19.8.3 extractor authority schema changed: extractors list missing")
    ex=[x for x in extractor_rows if x.get("feature_id")==F071]
    if len(ex)!=1:
        raise AuthorityError(f"F071 extractor record missing/ambiguous: count={len(ex)}")
    if ex[0].get("status")!="BLOCKED_PENDING_PIT_SECTOR_AUTHORITY":
        raise AuthorityError("F071 extractor status changed")
    if ex[0].get("source_authority")!="none yet":
        raise AuthorityError("F071 extractor source authority unexpectedly populated")
    if extractor.get("sector_relative_strength_state")!="BLOCKED_PENDING_PIT_SECTOR_AUTHORITY":
        raise AuthorityError("F071 top-level sector-relative-strength state changed")

    sw=structured.get("structured_feature_whitelist") or {}
    if sw.get("F012_whitelisted_count")!=42 or sw.get("F051_whitelisted_count")!=30:raise AuthorityError("F012/F051 authority changed")
    gov=structured.get("governance") or {}
    if gov.get("F071_materialized") is not False or gov.get("sector_relative_strength_still_blocked") is not True:raise AuthorityError("F071 structured governance changed")

    tc=gate.get("training_feature_contract") or {}
    if tc.get("structured_source_ids")!=["F012","F051"] or tc.get("blocked_feature_ids")!=["F071"] or tc.get("F071_excluded_from_training") is not True:raise AuthorityError("training feature contract changed")

    if "Historical PIT sector membership unavailable" not in hp.read_text(encoding="utf-8"):raise AuthorityError("historical PIT-sector denial missing")
    trend=tp.read_text(encoding="utf-8")
    if "SECTOR_ETFS" not in trend or "canonical_csv" not in trend:raise AuthorityError("current trend-sector mapping contract missing")

    report={
      "version":VERSION,"status":"READY","cycle":"M77.20_PROSPECTIVE_EDGE_CYCLE2",
      "prior_cycle_state":"CLOSED_EVIDENCE_PUBLISHED_NO_PRODUCTION_PROMOTION",
      "upstream_sha256":{"closure":H(cp),"feature_authority":H(fp),"extractor_authority":H(ep),"structured_target_authority":H(sp),"training_gate":H(gp),"historical_analytics_source":H(hp),"trend_service_source":H(tp)},
      "consumed_holdout_lock":{"period":"2023-01-01..2026-08-21","permanently_consumed":True,
          "reuse_for_cycle2_selection_authorized":False,"reuse_for_cycle2_retuning_authorized":False,
          "reuse_for_cycle2_threshold_search_authorized":False,"reuse_for_cycle2_feature_search_authorized":False,
          "reuse_for_cycle2_incremental_value_claim_authorized":False},
      "research_question":{"primary":"Does independently-certified point-in-time sector-relative strength (F071) add durable incremental directional information beyond the frozen M77.19 baseline feature set?",
          "new_feature_ids":["F071"],"feature_domain_under_test":"RELATIVE_STRENGTH_VS_MARKET_AND_SECTOR",
          "F012_status":"ALREADY_WHITELISTED_AND_MATERIALIZED_IN_PRIOR_99_COLUMN_MODEL_CONTRACT_NOT_A_NEW_CYCLE2_FEATURE",
          "F051_status":"ALREADY_WHITELISTED_AND_MATERIALIZED_IN_PRIOR_99_COLUMN_MODEL_CONTRACT_NOT_A_NEW_CYCLE2_FEATURE"},
      "pit_sector_contract":{"status":"PREREGISTERED_NOT_YET_CERTIFIED",
          "historical_current_mapping_backfill_prohibited":True,
          "current_canonical_csv_may_not_be_treated_as_historical_membership":True,
          "production_trend_sector_mapping_may_not_be_treated_as_historical_membership":True,
          "required_membership_semantics":["symbol","sector","effective_from_or_snapshot_date","effective_to_or_successor_boundary","source_identity","source_snapshot_or_record_identity"],
          "required_benchmark_semantics":["sector","benchmark_symbol","effective_from","effective_to_or_open_ended","benchmark_source_identity"],
          "membership_must_be_known_as_of_observation":True,"benchmark_must_exist_as_of_observation":True,
          "benchmark_pre_inception_substitution_authorized":False,
          "unknown_or_unavailable_membership_policy":"EXPLICIT_MISSING_F071_NO_INFERENCE",
          "survivorship_free_claim_requires_independent_certification":True},
      "F071_formula_preregistration":{"formula_may_not_be_materialized_until_pit_sector_authority_ready":True,
          "candidate_semantics_to_freeze_before_any_outcome_evaluation":{
              "rs_sector_13w":"symbol trailing 65 available sessions return minus point-in-time sector benchmark trailing 65 available sessions return",
              "rs_sector_26w":"symbol trailing 130 available sessions return minus point-in-time sector benchmark trailing 130 available sessions return"},
          "same_as_of_or_prior_only":True,"future_bar_access_for_feature_construction":False,
          "benchmark_fallback_to_SPY_authorized":False,"benchmark_fallback_to_current_sector_authorized":False,
          "cross_sector_imputation_authorized":False,"missingness_explicit":True},
      "partition_governance":{
          "development":{"period":"2004-11-19..2017-12-29","cycle2_use":"FEATURE_AUTHORITY_CONSTRUCTION_AND_DEVELOPMENT_ONLY_INCREMENTAL_DIAGNOSTICS"},
          "previous_validation":{"period":"2018-01-01..2022-12-30","cycle2_use":"NO_MODEL_OR_FEATURE_SELECTION; DESCRIPTIVE_SANITY_CHECK_ONLY_IF_LATER_EXPLICITLY_AUTHORIZED"},
          "consumed_final_holdout":{"period":"2023-01-01..2026-08-21","cycle2_use":"PROHIBITED_FOR_FEATURE_SELECTION_MODEL_SELECTION_RETUNING_THRESHOLD_SEARCH_OR_INCREMENTAL_VALUE_CLAIMS"},
          "new_untouched_prospective_evaluation":{"start":PROSPECTIVE_START,"end":"OPEN_ENDED_UNTIL_SEPARATELY_FROZEN_BEFORE_OUTCOME_ANALYSIS","capture_mode":"PROSPECTIVE_SHADOW_FEATURES_FIRST_TARGETS_MATURE_LATER","outcomes_may_not_be_opened_until_feature_snapshot_is_immutable":True}},
      "incremental_value_test_preregistration":{"comparison":"FROZEN_BASELINE_VS_FROZEN_BASELINE_PLUS_F071","paired_same_observation_population_required":True,
          "horizons":HORIZONS,"direction_label_policy":"DROP_ZERO_THEN_BINARY_UP_VS_DOWN",
          "primary_metric":"BALANCED_ACCURACY_DELTA_F071_MINUS_BASELINE","secondary_metrics":["ROC_AUC_DELTA","LOG_LOSS_DELTA","BRIER_SCORE_DELTA"],
          "analysis_model_role":"FIXED_MEASUREMENT_INSTRUMENT_NOT_MODEL_FAMILY_SELECTION","analysis_model":"MF1_REGULARIZED_LOGISTIC_DIRECTION",
          "frozen_prior_configs":{"5":{"C":10.0},"10":{"C":1.0},"20":{"C":0.1}},"threshold":0.5,
          "retuning_authorized":False,"new_hyperparameter_search_authorized":False,"new_threshold_search_authorized":False,
          "global_feature_selection_search_authorized":False,"interaction_search_authorized":False,
          "regime_conditioning_role":"DESCRIPTIVE_SECONDARY_ANALYSIS_ONLY_NOT_SELECTION",
          "prospective_advancement_rule":{"minimum_matured_binary_rows_per_horizon":10000,"mean_balanced_accuracy_delta_min":0.003,
              "all_horizons_delta_floor":-0.002,"positive_delta_horizons_min":2,
              "paired_date_cluster_bootstrap_lower_95ci_above_zero_horizons_min":2,
              "production_promotion_authorized_if_passed":False,"pass_only_authorizes_next_shadow_certification_stage":True}},
      "execution_state":{"pit_sector_authority_certified":False,"F071_materialized":False,
          "cycle2_development_incremental_diagnostics_performed":False,"cycle2_previous_validation_opened_for_selection":False,
          "consumed_final_holdout_opened_for_cycle2":False,"prospective_shadow_capture_started":False,
          "prospective_outcomes_opened":False,"prospective_scoring_performed":False,"cycle2_feature_accepted":False,
          "production_model_change_authorized":False,"production_authority_effect":False},
      "next_step":"BUILD_M77_20_1_PIT_SECTOR_MEMBERSHIP_AND_BENCHMARK_SOURCE_AUTHORITY_CENSUS"}

    oj=R(root,a.output_json);oc=R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    oj.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    rows=[
      {"domain":"PRIOR_CYCLE","item":"M77.19 Final Holdout","state":"PERMANENTLY_CONSUMED","selection_authorized":False},
      {"domain":"STRUCTURED_FEATURE","item":"F012","state":"ALREADY_IN_PRIOR_MODEL_CONTRACT","selection_authorized":False},
      {"domain":"STRUCTURED_FEATURE","item":"F051","state":"ALREADY_IN_PRIOR_MODEL_CONTRACT","selection_authorized":False},
      {"domain":"NEW_FEATURE","item":"F071","state":"BLOCKED_PENDING_PIT_SECTOR_AUTHORITY","selection_authorized":False},
      {"domain":"EVALUATION","item":"Prospective shadow start","state":PROSPECTIVE_START,"selection_authorized":False}]
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["domain","item","state","selection_authorized"]);w.writeheader();w.writerows(rows)

    print("=== M77.20.0 PROSPECTIVE EDGE CYCLE 2 PREREGISTRATION & CONSUMED-HOLDOUT LOCK ===")
    print("status: READY")
    print("prior_cycle_state: CLOSED_EVIDENCE_PUBLISHED_NO_PRODUCTION_PROMOTION")
    print("consumed_final_holdout_end:",CONSUMED_HOLDOUT_END)
    print("consumed_final_holdout_reuse_for_cycle2_selection_authorized: False")
    print("F012_status: ALREADY_WHITELISTED_AND_MATERIALIZED_IN_PRIOR_99_COLUMN_MODEL_CONTRACT")
    print("F051_status: ALREADY_WHITELISTED_AND_MATERIALIZED_IN_PRIOR_99_COLUMN_MODEL_CONTRACT")
    print("F071_status: BLOCKED_PENDING_PIT_SECTOR_AUTHORITY")
    print("historical_current_mapping_backfill_prohibited: True")
    print("benchmark_pre_inception_substitution_authorized: False")
    print("new_untouched_prospective_evaluation_start:",PROSPECTIVE_START)
    print("primary_incremental_metric: BALANCED_ACCURACY_DELTA_F071_MINUS_BASELINE")
    print("minimum_matured_binary_rows_per_horizon: 10000")
    print("mean_balanced_accuracy_delta_min: 0.003")
    print("production_promotion_authorized_if_passed: False")
    print("prospective_outcomes_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
if __name__=="__main__":main()
