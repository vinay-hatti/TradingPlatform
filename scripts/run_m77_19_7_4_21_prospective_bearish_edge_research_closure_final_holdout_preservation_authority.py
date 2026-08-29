#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from pathlib import Path
VERSION="M77.19.7.4.21-PROSPECTIVE-BEARISH-EDGE-RESEARCH-CLOSURE-FINAL-HOLDOUT-PRESERVATION-AUTHORITY-1.0"
EXPECTED_VALIDATION_VERSION="M77.19.7.4.20-AUTHORIZED-REGIME-CONDITIONED-VALIDATION-ONLY-EVALUATION-1.0"
EXPECTED_INSTABILITY_VERSION="M77.19.7.4.14-DEVELOPMENT-VALIDATION-REGIME-SHIFT-EDGE-INSTABILITY-FORENSICS-1.0"
FINAL_HOLDOUT_START="2023-01-01"
class ClosureError(RuntimeError): pass
def sha256_file(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for c in iter(lambda:f.read(1048576),b""): h.update(c)
 return h.hexdigest()
def load_json(p):
 with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
 p=Path(p)
 return p if p.exists() else root/p
def atomic_json(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); fd,t=tempfile.mkstemp(dir=p.parent);os.close(fd)
 try:
  with open(t,"w",encoding="utf-8") as f:json.dump(x,f,indent=2,sort_keys=True);f.write("\n")
  os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 a.add_argument("--validation-json",default="reports/m77_19_7_4_20_authorized_regime_conditioned_validation_only_evaluation.json")
 a.add_argument("--instability-json",default="reports/m77_19_7_4_14_development_validation_regime_shift_edge_instability_forensics.json")
 a.add_argument("--output-json",default="reports/m77_19_7_4_21_prospective_bearish_edge_research_closure_final_holdout_preservation_authority.json")
 a.add_argument("--output-csv",default="reports/m77_19_7_4_21_research_closure_registry.csv")
 x=a.parse_args(); root=Path(x.project_root).resolve();vp=resolve(root,x.validation_json);ip=resolve(root,x.instability_json)
 v=load_json(vp);i=load_json(ip)
 if v.get("version")!=EXPECTED_VALIDATION_VERSION or v.get("status")!="READY":raise ClosureError("7.4.20 invalid")
 if i.get("version")!=EXPECTED_INSTABILITY_VERSION or i.get("status")!="READY":raise ClosureError("7.4.14 invalid")
 g=v.get("validation_gate_result") or {};f=i.get("forensic_findings") or {}
 if g.get("candidate_family_survives_validation") is not False:raise ClosureError("survivor exists")
 if g.get("fully_surviving_candidate_count")!=0 or g.get("partially_surviving_candidate_count")!=0:raise ClosureError("survivor count nonzero")
 if g.get("failed_candidate_count")!=2 or g.get("final_holdout_open_authorized") is not False:raise ClosureError("validation closure mismatch")
 if f.get("all_authorized_candidates_failed_validation") is not True or f.get("development_validation_instability_present") is not True or f.get("final_holdout_remains_sealed") is not True:raise ClosureError("instability authority mismatch")
 closures=[
 {"research_branch":"ORIGINAL_PROSPECTIVE_BEARISH_CANDIDATES","status":"RETIRED_VALIDATION_FAILURE","basis":"H1/H3 Development rejection and H2/H4 Validation rejection","production_effect":False},
 {"research_branch":"REGIME_CONDITIONED_H4_GE10_RC1","status":"RETIRED_VALIDATION_FAILURE","basis":"Authorized Validation failed 5/10/20","production_effect":False},
 {"research_branch":"REGIME_CONDITIONED_H4_5_10_RC2","status":"RETIRED_VALIDATION_FAILURE","basis":"Authorized Validation failed 5/10/20; N below 300","production_effect":False}]
 r={"version":VERSION,"status":"READY","validation_authority_sha256":sha256_file(vp),"instability_authority_sha256":sha256_file(ip),
 "closure_state":{"prospective_bearish_edge_research_branch":"CLOSED_NO_CERTIFIED_CHAMPION","original_candidate_family_retired":True,"regime_conditioned_candidate_family_retired":True,"certified_prospective_bearish_champion_exists":False,"further_filter_rescue_search_authorized":False,"automatic_bearish_inversion_authorized":False},
 "research_closures":closures,
 "semantic_authority":{"stock_intelligence_bearish_state_role":"DESCRIPTIVE_STATE_EVIDENCE","bearish_state_is_certified_standalone_future_downside_probability":False,"prospective_edge_must_be_separate_from_descriptive_state":True,"economic_opportunity_must_be_separate_from_prospective_edge":True,"strategy_selection_must_be_downstream_of_certified_edge":True},
 "architecture_contract":{"stage_1":"DESCRIPTIVE_STATE","stage_2":"PROSPECTIVE_EDGE","stage_3":"ECONOMIC_OPPORTUNITY","stage_4":"STRATEGY_SELECTION","descriptive_bearish_state_may_remain_useful":True,"failed_prospective_certification_does_not_invalidate_state_detection":True},
 "final_holdout_preservation":{"start":FINAL_HOLDOUT_START,"opened_by_this_milestone":False,"read_by_this_milestone":False,"scored_by_this_milestone":False,"remains_pristine_for_materially_different_future_architecture":True,"reuse_to_rescue_closed_candidate_family_authorized":False},
 "production_governance":{"stock_intelligence_change_authorized":False,"scoring_change_authorized":False,"threshold_change_authorized":False,"weight_change_authorized":False,"decision_intelligence_change_authorized":False,"institutional_options_change_authorized":False,"portfolio_change_authorized":False,"execution_change_authorized":False,"management_change_authorized":False,"production_model_change_authorized":False,"production_authority_effect":False},
 "research_governance":{"new_candidate_scored":False,"threshold_search_or_optimization":False,"regime_search_or_optimization":False,"parameter_fitting":False,"classifier_training":False,"calibrator_fitting":False,"automatic_bearish_signal_inversion":False},
 "recommended_future_direction":{"continue_current_bearish_filter_search":False,"next_architecture_should_be_materially_different":True,"preserve_final_holdout_for_that_architecture":True},
 "next_step":"RETURN_TO_M77_PROGRAM_GOVERNANCE_AND_SELECT_MATERIALLY_DIFFERENT_PROSPECTIVE_EDGE_ARCHITECTURE_BEFORE_ANY_NEW_MODEL_RESEARCH"}
 oj=Path(x.output_json);oc=Path(x.output_csv)
 if not oj.is_absolute():oj=root/oj
 if not oc.is_absolute():oc=root/oc
 atomic_json(oj,r);oc.parent.mkdir(parents=True,exist_ok=True)
 rows=[{"record_type":"RESEARCH_BRANCH",**z} for z in closures]+[{"record_type":"AUTHORITY","research_branch":"FINAL_HOLDOUT","status":"SEALED","basis":"Preserve >=2023 for materially different future architecture","production_effect":False},{"record_type":"AUTHORITY","research_branch":"BEARISH_STATE_SEMANTICS","status":"DESCRIPTIVE_ONLY_NOT_CERTIFIED_PROSPECTIVE_EDGE","basis":"Prospective edge failed independent historical certification","production_effect":False}]
 with oc.open("w",encoding="utf-8",newline="") as q:
  w=csv.DictWriter(q,fieldnames=["record_type","research_branch","status","basis","production_effect"]);w.writeheader();w.writerows(rows)
 print("=== M77.19.7.4.21 PROSPECTIVE BEARISH EDGE RESEARCH CLOSURE & FINAL-HOLDOUT PRESERVATION AUTHORITY ===")
 for k,z in [("status","READY"),("prospective_bearish_edge_research_branch","CLOSED_NO_CERTIFIED_CHAMPION"),("original_candidate_family_retired",True),("regime_conditioned_candidate_family_retired",True),("certified_prospective_bearish_champion_exists",False),("further_filter_rescue_search_authorized",False),("stock_intelligence_bearish_state_role","DESCRIPTIVE_STATE_EVIDENCE"),("bearish_state_is_certified_standalone_future_downside_probability",False),("prospective_edge_must_be_separate_from_descriptive_state",True),("final_holdout_opened_by_this_milestone",False),("final_holdout_read_by_this_milestone",False),("final_holdout_scored_by_this_milestone",False),("final_holdout_remains_pristine_for_materially_different_future_architecture",True),("automatic_bearish_signal_inversion",False),("production_model_change_authorized",False),("production_authority_effect",False)]:print(f"{k}: {z}")
 print("next_step: "+r["next_step"]);print("report:",oj);print("csv:",oc);return 0
if __name__=="__main__":raise SystemExit(main())
