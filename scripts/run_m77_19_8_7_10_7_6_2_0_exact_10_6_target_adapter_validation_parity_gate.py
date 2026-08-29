#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys,tempfile,shutil
from pathlib import Path
EXPECTED_SOURCE_SHA="5301df749eb7dc001cd725959fd62265b484e8e0afe4a09609ebb0cad3b60009"
EXPECTED_ADAPTER_SHA="267170fb324e76c6c0c3bcb1fb090a7e649ba88fcf697d52d8b2614b32366fa4"
class GateError(RuntimeError):pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def J(p):return json.loads(Path(p).read_text())
def sem_file(p):
 h=hashlib.sha256();n=0
 with gzip.open(p,"rt",encoding="utf-8") as f:
  for line in f:
   if not line.strip():continue
   obj=json.loads(line);h.update(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode());h.update(b"\n");n+=1
 return h.hexdigest(),n
def tree(root):
 out={};rows=0
 for p in sorted(Path(root).glob("h*/*.jsonl.gz")):
  rel=str(p.relative_to(root));x,n=sem_file(p);out[rel]=x;rows+=n
 return out,rows
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 ap.add_argument("--source-script",default="scripts/run_m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.py")
 ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_7_10_6_partition_parameterized_target_materialization_certified.py")
 ap.add_argument("--validation-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
 ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix")
 ap.add_argument("--validation-backfill-authority-json",default="reports/m77_19_8_7_10_5_2_4_exact_8_4_3_validation_backfill_matrix_materialization.json")
 ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
 ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
 ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
 ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill")
 ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
 ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_6_2_0_exact_10_6_target_adapter_validation_parity_gate.json")
 a=ap.parse_args();r=Path(a.project_root).resolve()
 if sha(r/a.source_script)!=EXPECTED_SOURCE_SHA:raise GateError("canonical 10.6 source SHA mismatch")
 if sha(r/a.adapter_script)!=EXPECTED_ADAPTER_SHA:raise GateError("parameterized adapter SHA mismatch")
 old=J(r/a.validation_authority_json)
 if old.get("status")!="READY" or old.get("validation_targets_materialized") is not True:raise GateError("existing Validation target authority invalid")
 existing,existing_rows=tree(r/a.validation_target_root)
 tmp=Path(tempfile.mkdtemp(prefix="m77_10_7_6_2_0_",dir=r/"research_data"))
 try:
  outroot=tmp/"targets";oj=tmp/"report.json";oc=tmp/"summary.csv"
  cmd=[sys.executable,str(r/a.adapter_script),"--project-root",str(r),"--active-partition-label","VALIDATION","--partition-start","2018-01-01","--partition-end","2022-12-31",
   "--expected-feature-rows","141567","--expected-feature-symbols","570","--validation-backfill-authority-json",a.validation_backfill_authority_json,
   "--training-gate-json",a.training_gate_json,"--development-target-authority-json",a.development_target_authority_json,
   "--development-feature-root",a.development_feature_root,"--validation-feature-root",a.validation_feature_root,
   "--daily-materialization-root",a.daily_materialization_root,"--output-root",str(outroot),"--output-json",str(oj),"--output-csv",str(oc)]
  rc=subprocess.call(cmd,cwd=r)
  if rc!=0:raise GateError(f"adapter Validation parity execution failed returncode={rc}")
  regen,regen_rows=tree(outroot)
  missing=sorted(set(existing)-set(regen));extra=sorted(set(regen)-set(existing));mismatch=sorted(k for k in set(existing)&set(regen) if existing[k]!=regen[k])
  if missing or extra or mismatch or existing_rows!=regen_rows:raise GateError(f"Validation semantic parity mismatch missing={len(missing)} extra={len(extra)} mismatch={len(mismatch)} rows={existing_rows}/{regen_rows}")
  rr=J(oj)
  if rr.get("status")!="READY":raise GateError("regenerated Validation report not READY")
  out={"version":"M77.19.8.7.10.7.6.2.0-EXACT-10.6-TARGET-ADAPTER-VALIDATION-PARITY-GATE-1.0","status":"READY",
   "canonical_10_6_source_sha256":EXPECTED_SOURCE_SHA,"parameterized_adapter_sha256":EXPECTED_ADAPTER_SHA,
   "validation_target_file_count":len(existing),"validation_target_row_count":existing_rows,
   "missing_file_count":0,"extra_file_count":0,"semantic_mismatch_file_count":0,
   "validation_target_semantic_parity_certified":True,"target_formula_reimplementation_performed":False,
   "target_label_mapping_change_performed":False,"final_holdout_targets_opened":False,"final_holdout_outcomes_opened":False,
   "final_holdout_scoring_performed":False,"model_family_champion_selected":False,"production_authority_effect":False,
   "next_step":"RUN_M77_19_8_7_10_7_6_2_1_FINAL_HOLDOUT_TARGET_MATERIALIZATION"}
  (r/a.output_json).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
  print("=== M77.19.8.7.10.7.6.2.0 EXACT 10.6 TARGET ADAPTER VALIDATION PARITY GATE ===")
  print("status: READY");print("validation_target_file_count:",len(existing));print("validation_target_row_count:",existing_rows)
  print("missing_file_count: 0");print("extra_file_count: 0");print("semantic_mismatch_file_count: 0")
  print("validation_target_semantic_parity_certified: True");print("target_formula_reimplementation_performed: False")
  print("final_holdout_targets_opened: False");print("final_holdout_scoring_performed: False");print("production_authority_effect: False")
  print("next_step:",out["next_step"]);print("report:",r/a.output_json)
 finally:
  shutil.rmtree(tmp,ignore_errors=True)
if __name__=="__main__":main()
