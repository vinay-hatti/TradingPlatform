#!/usr/bin/env python3
import argparse,hashlib,json,ast
from pathlib import Path
EXPECTED_SOURCE_SHA={"backfill": "21550a07c6d05afaad0de888673963fd1e52cba6333a6b8a40474b2a4f832f65", "base": "eb223744f3762976d9e67ed82843ed90d10a136810764b20e982a58cb0d0b8cf", "context": "f1aa47fc78d7404f513aa1405e4401ca70ee2e06cb63a298063a3a068e2b891a"}
EXPECTED_ADAPTER_SHA={"run_m77_19_7_4_16_final_holdout_partition_parameterized_certified.py": "04a13d955353e42b50df9d0d72017edb8630d2a0f3e9a65c57161e2498c8ee6f", "run_m77_19_8_2_final_holdout_routing_parameterized_certified.py": "12e1e4b46c937dff8cfac127a254ea4d19d4421666a39433b47df1ee3fdc7102", "run_m77_19_8_4_3_final_holdout_row_admission_parameterized_certified.py": "ccdc4a3d26cc1f25f537f6a01f03ff3acb0311f7e7c73134b13331955f95fd4b"}
SOURCE_FILES={
"context":"scripts/run_m77_19_7_4_16_point_in_time_regime_context_materialization_authority.py",
"base":"scripts/run_m77_19_8_2_partition_routing_parameterized_certified.py",
"backfill":"scripts/run_m77_19_8_4_3_partition_row_admission_parameterized_certified.py"}
ADAPTER_FILES={
"context":"scripts/run_m77_19_7_4_16_final_holdout_partition_parameterized_certified.py",
"base":"scripts/run_m77_19_8_2_final_holdout_routing_parameterized_certified.py",
"backfill":"scripts/run_m77_19_8_4_3_final_holdout_row_admission_parameterized_certified.py"}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
 ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_6_0_exact_final_holdout_feature_adapter_certification_gate.json")
 a=ap.parse_args();r=Path(a.project_root).resolve()
 protocol=json.loads((r/a.protocol_json).read_text())
 if protocol.get("status")!="READY" or protocol.get("final_holdout_protocol_preregistered") is not True:raise RuntimeError("10.7.5 protocol invalid")
 if protocol.get("final_holdout_feature_materialization_authorized") is not True or protocol.get("final_holdout_scoring_authorized_by_this_step") is not False:raise RuntimeError("10.7.5 materialization/scoring governance invalid")
 if protocol.get("final_holdout_opened") is not False or protocol.get("production_authority_effect") is not False:raise RuntimeError("Final Holdout already opened or production affected")
 reg=[]
 for k in ("context","base","backfill"):
  sp=r/SOURCE_FILES[k];apath=r/ADAPTER_FILES[k]
  if sha(sp)!=EXPECTED_SOURCE_SHA[k]:raise RuntimeError(f"{k} canonical source SHA mismatch")
  expected=EXPECTED_ADAPTER_SHA[Path(ADAPTER_FILES[k]).name]
  if sha(apath)!=expected:raise RuntimeError(f"{k} adapter SHA mismatch")
  ast.parse(apath.read_text())
  reg.append({"component":k,"source_sha256":sha(sp),"adapter_sha256":sha(apath),"compiled_ast":True})
 out={"version":"M77.19.8.7.10.7.6.0-EXACT-FINAL-HOLDOUT-FEATURE-ADAPTER-CERTIFICATION-1.0","status":"READY",
 "adapter_registry":reg,"context_adapter_certified":True,"base_matrix_adapter_certified":True,"backfill_adapter_certified":True,
 "final_holdout_rows_read_by_this_step":False,"final_holdout_context_materialized":False,"final_holdout_feature_matrix_materialized":False,
 "final_holdout_targets_opened":False,"final_holdout_scoring_performed":False,"model_family_champion_selected":False,
 "production_authority_effect":False,
 "next_step":"RUN_M77_19_8_7_10_7_6_1_FINAL_HOLDOUT_CONTEXT_AND_FEATURE_MATRIX_MATERIALIZATION"}
 (r/a.output_json).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print("=== M77.19.8.7.10.7.6.0 EXACT FINAL HOLDOUT FEATURE ADAPTER CERTIFICATION GATE ===")
 print("status: READY");print("context_adapter_certified: True");print("base_matrix_adapter_certified: True");print("backfill_adapter_certified: True")
 print("final_holdout_rows_read_by_this_step: False");print("final_holdout_feature_matrix_materialized: False");print("final_holdout_targets_opened: False")
 print("final_holdout_scoring_performed: False");print("production_authority_effect: False");print("next_step:",out["next_step"]);print("report:",r/a.output_json)
if __name__=="__main__":main()
