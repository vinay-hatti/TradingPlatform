#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

VERSION="M77.20.2-EXTERNAL-HISTORICAL-PIT-SECTOR-SOURCE-DECISION-PROSPECTIVE-ONLY-RESEARCH-DESIGN-GATE-1.0"
PROSPECTIVE_START="2026-08-24"

class GateError(RuntimeError): pass

def R(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def J(p):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--cycle2-json",default="reports/m77_20_0_prospective_edge_cycle2_preregistration_consumed_holdout_lock_authority.json")
    ap.add_argument("--census-json",default="reports/m77_20_1_pit_sector_membership_benchmark_source_authority_census.json")
    ap.add_argument("--output-json",default="reports/m77_20_2_external_historical_pit_sector_source_decision_prospective_only_research_design_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_20_2_prospective_only_design_registry.csv")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    c2p=R(root,a.cycle2_json)
    cp=R(root,a.census_json)
    if not c2p.exists() or not cp.exists():
        raise GateError("required M77.20 upstream authority missing")

    c2=J(c2p)
    census=J(cp)

    if c2.get("status")!="READY" or c2.get("cycle")!="M77.20_PROSPECTIVE_EDGE_CYCLE2":
        raise GateError("M77.20.0 authority invalid")
    if census.get("status")!="READY":
        raise GateError("M77.20.1 census invalid")
    if census.get("census_conclusion")!="BLOCKED_NO_REPO_CERTIFIED_HISTORICAL_PIT_SECTOR_MEMBERSHIP_SOURCE":
        raise GateError("M77.20.1 census conclusion changed")
    if census.get("historical_pit_sector_membership_authority_certified") is not False:
        raise GateError("historical PIT sector authority unexpectedly certified")
    if census.get("historical_F071_materialization_authorized") is not False:
        raise GateError("historical F071 unexpectedly authorized")
    if census.get("prospective_membership_snapshot_capture_authorized") is not True:
        raise GateError("prospective membership capture not authorized")
    if census.get("prospective_sector_benchmark_snapshot_capture_authorized") is not True:
        raise GateError("prospective benchmark capture not authorized")
    if census.get("prospective_outcomes_opened") is not False:
        raise GateError("prospective outcomes already opened")

    consumed=(c2.get("consumed_holdout_lock") or {})
    if consumed.get("permanently_consumed") is not True:
        raise GateError("consumed Final Holdout lock missing")
    for k in (
        "reuse_for_cycle2_selection_authorized",
        "reuse_for_cycle2_retuning_authorized",
        "reuse_for_cycle2_threshold_search_authorized",
        "reuse_for_cycle2_feature_search_authorized",
        "reuse_for_cycle2_incremental_value_claim_authorized",
    ):
        if consumed.get(k) is not False:
            raise GateError(f"consumed Final Holdout lock relaxed: {k}")

    pgov=c2.get("partition_governance") or {}
    prospective=pgov.get("new_untouched_prospective_evaluation") or {}
    if prospective.get("start")!=PROSPECTIVE_START:
        raise GateError("prospective start changed")
    if prospective.get("outcomes_may_not_be_opened_until_feature_snapshot_is_immutable") is not True:
        raise GateError("feature-before-outcome boundary missing")

    decision={
      "historical_external_source_selected":False,
      "historical_external_source_certification_attempted_by_this_step":False,
      "historical_backfill_route":"CLOSED",
      "prospective_only_route_selected":True,
      "decision_basis":"NO_REPO_CERTIFIED_HISTORICAL_PIT_SOURCE_AND_OUTCOMES_STILL_CLOSED",
      "decision_made_before_prospective_outcomes_opened":True,
    }

    prospective_capture_contract={
      "capture_start":PROSPECTIVE_START,
      "capture_cadence":"DAILY_SNAPSHOT_ON_EACH_MARKET_SESSION_OR_GOVERNED_DAILY_INGESTION_RUN",
      "membership_snapshot_required_fields":[
          "symbol","sector","snapshot_date","source_identity","source_record_identity_or_snapshot_hash"
      ],
      "benchmark_snapshot_required_fields":[
          "sector","benchmark_symbol","snapshot_date","source_identity","source_record_identity_or_snapshot_hash"
      ],
      "snapshot_immutability_required":True,
      "historical_rewrite_authorized":False,
      "retroactive_sector_reclassification_authorized":False,
      "retroactive_benchmark_substitution_authorized":False,
      "unknown_membership_policy":"EXPLICIT_MISSING_F071",
      "unknown_benchmark_policy":"EXPLICIT_MISSING_F071",
      "benchmark_pre_inception_substitution_authorized":False,
      "future_outcome_access_for_snapshot_capture":False,
      "prospective_outcomes_opened":False,
    }

    prospective_f071_contract={
      "feature_id":"F071",
      "materialization_scope":"PROSPECTIVE_ONLY",
      "historical_development_materialization_authorized":False,
      "historical_validation_materialization_authorized":False,
      "consumed_final_holdout_materialization_authorized":False,
      "prospective_feature_materialization_authorized_after_snapshot_capture_certification":True,
      "same_as_of_or_prior_snapshot_only":True,
      "rs_sector_13w_formula":"symbol trailing 65 available sessions return minus captured sector benchmark trailing 65 available sessions return",
      "rs_sector_26w_formula":"symbol trailing 130 available sessions return minus captured sector benchmark trailing 130 available sessions return",
      "formula_change_authorized":False,
      "current_sector_backfill_authorized":False,
      "benchmark_fallback_to_SPY_authorized":False,
      "cross_sector_imputation_authorized":False,
    }

    evaluation_contract={
      "research_mode":"PROSPECTIVE_SHADOW_INCREMENTAL_VALUE_ONLY",
      "baseline_feature_contract":"FROZEN_M77_19_BASELINE",
      "comparison_feature_contract":"FROZEN_M77_19_BASELINE_PLUS_PROSPECTIVE_F071",
      "same_observation_population_required":True,
      "outcomes_opening_prerequisites":[
          "PROSPECTIVE_MEMBERSHIP_SNAPSHOT_CAPTURE_CERTIFIED",
          "PROSPECTIVE_BENCHMARK_SNAPSHOT_CAPTURE_CERTIFIED",
          "PROSPECTIVE_F071_FEATURE_SNAPSHOT_IMMUTABLE",
          "MINIMUM_MATURED_SAMPLE_RULE_MET"
      ],
      "minimum_matured_binary_rows_per_horizon":10000,
      "horizons":[5,10,20],
      "analysis_model":"MF1_REGULARIZED_LOGISTIC_DIRECTION",
      "frozen_configs":{"5":{"C":10.0},"10":{"C":1.0},"20":{"C":0.1}},
      "decision_threshold":0.5,
      "retuning_authorized":False,
      "threshold_search_authorized":False,
      "feature_selection_search_authorized":False,
      "hyperparameter_search_authorized":False,
      "family_selection_authorized":False,
      "primary_metric":"BALANCED_ACCURACY_DELTA_F071_MINUS_BASELINE",
      "advancement_rule":(c2.get("incremental_value_test_preregistration") or {}).get("prospective_advancement_rule"),
      "production_promotion_authorized_if_passed":False,
    }

    execution_state={
      "prospective_only_design_certified":True,
      "historical_F071_branch_closed":True,
      "prospective_membership_snapshot_capture_started":False,
      "prospective_benchmark_snapshot_capture_started":False,
      "prospective_membership_snapshot_capture_certified":False,
      "prospective_benchmark_snapshot_capture_certified":False,
      "prospective_F071_materialized":False,
      "prospective_outcomes_opened":False,
      "prospective_scoring_performed":False,
      "cycle2_feature_accepted":False,
      "production_authority_effect":False,
    }

    report={
      "version":VERSION,
      "status":"READY",
      "upstream_sha256":{"m77_20_0":H(c2p),"m77_20_1":H(cp)},
      "decision":decision,
      "prospective_capture_contract":prospective_capture_contract,
      "prospective_F071_contract":prospective_f071_contract,
      "evaluation_contract":evaluation_contract,
      "execution_state":execution_state,
      "next_step":"BUILD_M77_20_3_PROSPECTIVE_SECTOR_MEMBERSHIP_AND_BENCHMARK_SNAPSHOT_CAPTURE_AUTHORITY",
    }

    oj=R(root,a.output_json)
    oc=R(root,a.output_csv)
    oj.parent.mkdir(parents=True,exist_ok=True)
    oj.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    rows=[
      {"domain":"DECISION","item":"historical_external_source_selected","value":False},
      {"domain":"DECISION","item":"prospective_only_route_selected","value":True},
      {"domain":"HISTORICAL","item":"historical_F071_branch_closed","value":True},
      {"domain":"PROSPECTIVE","item":"capture_start","value":PROSPECTIVE_START},
      {"domain":"PROSPECTIVE","item":"outcomes_opened","value":False},
      {"domain":"PRODUCTION","item":"production_authority_effect","value":False},
    ]
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["domain","item","value"])
        w.writeheader();w.writerows(rows)

    print("=== M77.20.2 EXTERNAL HISTORICAL PIT SOURCE DECISION / PROSPECTIVE-ONLY RESEARCH DESIGN GATE ===")
    print("status: READY")
    print("historical_external_source_selected: False")
    print("historical_backfill_route: CLOSED")
    print("prospective_only_route_selected: True")
    print("decision_made_before_prospective_outcomes_opened: True")
    print("prospective_capture_start:",PROSPECTIVE_START)
    print("snapshot_immutability_required: True")
    print("retroactive_sector_reclassification_authorized: False")
    print("retroactive_benchmark_substitution_authorized: False")
    print("historical_development_F071_materialization_authorized: False")
    print("consumed_final_holdout_F071_materialization_authorized: False")
    print("prospective_F071_materialization_authorized_after_snapshot_capture_certification: True")
    print("minimum_matured_binary_rows_per_horizon: 10000")
    print("retuning_authorized: False")
    print("production_promotion_authorized_if_passed: False")
    print("prospective_outcomes_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj)
    print("csv:",oc)

if __name__=="__main__":
    main()
