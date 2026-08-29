#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path
VERSION="M77.19.8.1-POINT-IN-TIME-PROSPECTIVE-EDGE-FEATURE-AUTHORITY-1.0"
EXPECTED_ARCH_VERSION="M77.19.8-PROSPECTIVE-EDGE-INTELLIGENCE-ARCHITECTURE-MODEL-FAMILY-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
FINAL_HOLDOUT_START="2023-01-01"
FEATURES=[
{"id":"F001","domain":"PRICE_TREND_AND_MOMENTUM","name":"overall_score","source":"native_replay_row.overall_score","type":"continuous","transform":"RAW","missing":"FAIL_ROW_IF_REPLAYED_AND_MISSING"},
{"id":"F002","domain":"PRICE_TREND_AND_MOMENTUM","name":"profile_confidence","source":"profile.confidence","type":"continuous","transform":"RAW","missing":"FAIL_ROW_IF_REPLAYED_AND_MISSING"},
{"id":"F003","domain":"PRICE_TREND_AND_MOMENTUM","name":"direction_state","source":"profile.direction","type":"categorical","transform":"FIXED_ENUM_ONE_HOT_LATER","missing":"UNKNOWN_CATEGORY"},
{"id":"F010","domain":"MULTITIMEFRAME_ALIGNMENT","name":"alignment_score","source":"profile.alignment_score","type":"continuous","transform":"RAW","missing":"EXPLICIT_NULL"},
{"id":"F011","domain":"MULTITIMEFRAME_ALIGNMENT","name":"primary_timeframe","source":"profile.primary_timeframe","type":"categorical","transform":"FIXED_ENUM_ONE_HOT_LATER","missing":"UNKNOWN_CATEGORY"},
{"id":"F012","domain":"MULTITIMEFRAME_ALIGNMENT","name":"timeframe_states_payload","source":"profile.timeframe_states","type":"structured","transform":"FLATTEN_PREDECLARED_NUMERIC_AND_ENUM_FIELDS_ONLY","missing":"EXPLICIT_MISSINGNESS_FLAGS"},
{"id":"F020","domain":"VOLATILITY_AND_RANGE","name":"atr_1d","source":"profile.timeframe_states.1d.*ATR_NATIVE_FIELD*","type":"continuous","transform":"RAW_IF_NATIVE_FIELD_PRESENT","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F021","domain":"VOLATILITY_AND_RANGE","name":"atr_normalized","source":"same_as_of_ATR/reference_price","type":"continuous","transform":"ATR_DIV_REFERENCE_PRICE","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F030","domain":"SUPPORT_RESISTANCE_AND_STRUCTURE","name":"nearest_support_distance_pct","source":"profile.support_levels + same_as_of_reference_price","type":"continuous","transform":"SIGNED_DISTANCE_TO_NEAREST_LEVEL","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F031","domain":"SUPPORT_RESISTANCE_AND_STRUCTURE","name":"nearest_resistance_distance_pct","source":"profile.resistance_levels + same_as_of_reference_price","type":"continuous","transform":"SIGNED_DISTANCE_TO_NEAREST_LEVEL","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F032","domain":"SUPPORT_RESISTANCE_AND_STRUCTURE","name":"support_level_count","source":"profile.support_levels","type":"count","transform":"COUNT","missing":"ZERO_IF_EMPTY_LIST"},
{"id":"F033","domain":"SUPPORT_RESISTANCE_AND_STRUCTURE","name":"resistance_level_count","source":"profile.resistance_levels","type":"count","transform":"COUNT","missing":"ZERO_IF_EMPTY_LIST"},
{"id":"F040","domain":"BREAKOUT_BREAKDOWN_STATE","name":"breakout_state","source":"profile.breakout.state","type":"categorical","transform":"FIXED_ENUM_ONE_HOT_LATER","missing":"UNKNOWN_CATEGORY"},
{"id":"F050","domain":"PARTICIPATION_AND_VOLUME","name":"participation_state","source":"profile.participation.state","type":"categorical","transform":"FIXED_ENUM_ONE_HOT_LATER","missing":"UNKNOWN_CATEGORY"},
{"id":"F051","domain":"PARTICIPATION_AND_VOLUME","name":"institutional_volume_state","source":"profile.institutional_volume","type":"structured","transform":"FLATTEN_PREDECLARED_NUMERIC_AND_ENUM_FIELDS_ONLY","missing":"EXPLICIT_MISSINGNESS_FLAGS"},
{"id":"F060","domain":"MARKET_REGIME_AND_BREADTH","name":"breadth_bullish_fraction","source":"m77_19_7_4_16.breadth_bullish_fraction","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F061","domain":"MARKET_REGIME_AND_BREADTH","name":"breadth_bearish_fraction","source":"m77_19_7_4_16.breadth_bearish_fraction","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F062","domain":"MARKET_REGIME_AND_BREADTH","name":"spy_return_13w","source":"m77_19_7_4_16.spy_return_13w","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F063","domain":"MARKET_REGIME_AND_BREADTH","name":"spy_return_26w","source":"m77_19_7_4_16.spy_return_26w","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F064","domain":"MARKET_REGIME_AND_BREADTH","name":"spy_realized_vol_26w","source":"m77_19_7_4_16.spy_realized_vol_26w_annualized","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F065","domain":"MARKET_REGIME_AND_BREADTH","name":"spy_drawdown_52w","source":"m77_19_7_4_16.spy_drawdown_from_52w_peak","type":"continuous","transform":"RAW","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F070","domain":"RELATIVE_STRENGTH_VS_MARKET_AND_SECTOR","name":"relative_strength_vs_spy_proxy","source":"same_as_of symbol trailing return minus SPY trailing return","type":"continuous","transform":"FIXED_13W_AND_26W_LATER","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F071","domain":"RELATIVE_STRENGTH_VS_MARKET_AND_SECTOR","name":"relative_strength_vs_sector","source":"PIT_SECTOR_BENCHMARK_REQUIRED","type":"continuous","transform":"NOT_MATERIALIZED_UNTIL_SECTOR_PIT_AUTHORITY_EXISTS","missing":"NOT_AVAILABLE_AUTHORITY_BLOCKED"},
{"id":"F080","domain":"DRAW_DOWN_AND_DISTANCE_FROM_EXTREMES","name":"symbol_drawdown_from_52w_peak","source":"frozen symbol daily history prefix","type":"continuous","transform":"CURRENT_CLOSE_DIV_TRAILING_52W_PEAK_MINUS_1","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F081","domain":"DRAW_DOWN_AND_DISTANCE_FROM_EXTREMES","name":"distance_from_52w_low","source":"frozen symbol daily history prefix","type":"continuous","transform":"CURRENT_CLOSE_DIV_TRAILING_52W_LOW_MINUS_1","missing":"EXPLICIT_MISSINGNESS_FLAG"},
{"id":"F090","domain":"STATE_TRANSITION_AND_PERSISTENCE","name":"direction_state_age_observations","source":"prior PIT replay direction states only","type":"count","transform":"RUN_LENGTH","missing":"ZERO_AT_FIRST_OBSERVATION"},
{"id":"F091","domain":"STATE_TRANSITION_AND_PERSISTENCE","name":"direction_changed_from_prior","source":"prior PIT replay direction state only","type":"boolean","transform":"BOOLEAN","missing":"FALSE_AT_FIRST_OBSERVATION"}]
PROHIBITED=["future_forward_return","future_direction_label","future_SPY_return","validation_pass_fail","final_holdout_result","closed_H1_H2_H3_H4_identity","regime_conditioned_candidate_identity","symbol_identity_or_ticker_one_hot","post_as_of_corporate_action_information"]
class AuthorityError(RuntimeError):pass
def sha256_file(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for c in iter(lambda:f.read(1048576),b""):h.update(c)
 return h.hexdigest()
def load_json(p):
 with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
 p=Path(p)
 return p if p.exists() else root/p
def atomic_json(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);fd,t=tempfile.mkstemp(dir=p.parent);os.close(fd)
 try:
  with open(t,"w",encoding="utf-8") as f:json.dump(x,f,indent=2,sort_keys=True);f.write("\n")
  os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 a.add_argument("--architecture-json",default="reports/m77_19_8_prospective_edge_intelligence_architecture_model_family_preregistration_authority.json")
 a.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
 a.add_argument("--regime-context-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
 a.add_argument("--output-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
 a.add_argument("--output-csv",default="reports/m77_19_8_1_feature_registry.csv")
 x=a.parse_args();root=Path(x.project_root).resolve();ap=resolve(root,x.architecture_json);rp=resolve(root,x.replay_authority_json);cp=resolve(root,x.regime_context_json)
 arch=load_json(ap);replay=load_json(rp);ctx=load_json(cp)
 if arch.get("version")!=EXPECTED_ARCH_VERSION or arch.get("status")!="READY":raise AuthorityError("M77.19.8 architecture authority invalid")
 if sha256_file(rp)!=EXPECTED_REPLAY_SHA:raise AuthorityError("replay authority SHA mismatch")
 if replay.get("successful_symbol_cadence_replay_count")!=602:raise AuthorityError("expected 602 replayed symbols")
 if ctx.get("status")!="READY":raise AuthorityError("PIT regime context authority invalid")
 if ctx.get("final_holdout_protection",{}).get("context_rows_materialized")!=0:raise AuthorityError("Final Holdout context materialized")
 domains=sorted(set(z["domain"] for z in FEATURES))
 missing=sorted(set(arch.get("feature_domains") or [])-set(domains))
 if missing:raise AuthorityError("missing domains: "+str(missing))
 if len({z["id"] for z in FEATURES})!=len(FEATURES) or len({z["name"] for z in FEATURES})!=len(FEATURES):raise AuthorityError("duplicate feature")
 r={"version":VERSION,"status":"READY","architecture_authority_sha256":sha256_file(ap),"replay_authority_sha256":EXPECTED_REPLAY_SHA,"regime_context_authority_sha256":sha256_file(cp),
 "feature_count":len(FEATURES),"feature_domain_count":len(domains),"feature_domains":domains,"features":FEATURES,"prohibited_features":PROHIBITED,
 "materialization_contract":{"point_in_time_only":True,"same_as_of_or_prior_only":True,"future_information_access":False,"future_outcomes_used_as_features":False,"validation_results_used_as_features":False,"final_holdout_results_used_as_features":False,"symbol_identity_feature":False,"closed_hypothesis_identity_feature":False,"missingness_explicit":True,"raw_structured_payloads_may_not_enter_models_directly":True,"structured_payloads_require_separate_field_preregistration_before_flattening":True,"sector_relative_strength_blocked_until_pit_sector_authority":True},
 "transformation_governance":{"standardization_parameters_fit":False,"categorical_vocabulary_fit":False,"imputation_parameters_fit":False,"feature_selection_performed":False,"interaction_search_performed":False,"nonlinear_transformation_search_performed":False,"development_only_fit_required_later":True},
 "execution_state":{"feature_matrix_materialized":False,"development_training_matrix_materialized":False,"validation_matrix_materialized":False,"final_holdout_matrix_materialized":False,"models_trained":False,"models_scored":False,"validation_opened_for_new_architecture":False,"final_holdout_opened":False,"production_model_change_authorized":False,"production_authority_effect":False},
 "next_step":"BUILD_M77_19_8_2_DEVELOPMENT_ONLY_FEATURE_MATRIX_MATERIALIZATION_AND_SCHEMA_VALIDATION"}
 oj=Path(x.output_json);oc=Path(x.output_csv)
 if not oj.is_absolute():oj=root/oj
 if not oc.is_absolute():oc=root/oc
 atomic_json(oj,r);oc.parent.mkdir(parents=True,exist_ok=True)
 with oc.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=["id","domain","name","source","type","transform","missing"]);w.writeheader();w.writerows(FEATURES)
 print("=== M77.19.8.1 POINT-IN-TIME PROSPECTIVE EDGE FEATURE AUTHORITY ===")
 for k,v in [("status","READY"),("feature_count",len(FEATURES)),("feature_domain_count",len(domains)),("feature_domains",domains),("prohibited_feature_count",len(PROHIBITED)),("point_in_time_only",True),("future_information_access",False),("symbol_identity_feature",False),("closed_hypothesis_identity_feature",False),("sector_relative_strength_blocked_until_pit_sector_authority",True),("feature_matrix_materialized",False),("models_trained",False),("validation_opened_for_new_architecture",False),("final_holdout_opened",False),("production_model_change_authorized",False),("production_authority_effect",False)]:print(f"{k}: {v}")
 print("next_step: "+r["next_step"]);print("report:",oj);print("csv:",oc);return 0
if __name__=="__main__":raise SystemExit(main())
