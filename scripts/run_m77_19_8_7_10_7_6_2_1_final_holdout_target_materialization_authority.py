#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json,subprocess,sys
from collections import Counter
from pathlib import Path

HORIZONS=(5,10,20);HOLDOUT_START="2023-01-01"
class TargetError(RuntimeError):pass
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def iter_gz(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def scan(root,start,end):
    out={}
    for h in HORIZONS:
        files=sorted((Path(root)/f"h{h}").glob("*.jsonl.gz"));rows=0;labels=Counter();first=None;last=None;bad_partition=0;bad_window=0;bad_h=0;bad_future=0
        seen=set()
        for p in files:
            for r in iter_gz(p):
                rows+=1;d=str(r.get("as_of") or "")[:10];td=str(r.get("target_session") or "")[:10]
                key=(r.get("symbol"),d)
                if key in seen:raise TargetError(f"h{h}: duplicate target key {key}")
                seen.add(key)
                first=d if first is None or d<first else first;last=d if last is None or d>last else last
                if r.get("partition")!="FINAL_HOLDOUT":bad_partition+=1
                if not(start<=d<=end) or not(d<td<=end):bad_window+=1
                if int(r.get("horizon_sessions",-1))!=h:bad_h+=1
                if r.get("future_bars_used_for_target_labeling_only") is not True:bad_future+=1
                lab=r.get("T_DIRECTION")
                if lab not in ("UP","DOWN","ZERO"):raise TargetError(f"h{h}: noncanonical direction {lab}")
                labels[lab]+=1
                for k in ("T_ABS_RET","T_REL_SPY_RET"):
                    if k not in r:raise TargetError(f"h{h}: target field missing {k}")
        out[h]={"file_count":len(files),"row_count":rows,"labels":dict(labels),"first_as_of":first,"last_as_of":last,
                "bad_partition":bad_partition,"bad_window":bad_window,"bad_horizon":bad_h,"bad_future_flag":bad_future}
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_7_10_7_6_1_final_holdout_context_feature_matrix_materialization.json")
    ap.add_argument("--target-adapter-parity-json",default="reports/m77_19_8_7_10_7_6_2_0_exact_10_6_target_adapter_validation_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_7_10_6_partition_parameterized_target_materialization_certified.py")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--final-holdout-feature-root",default="research_data/m77_19_8_7_10_7_6_1/final_holdout_feature_matrix_certified_backfill")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_7_6_2_1/final_holdout_target_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_6_2_1_final_holdout_target_materialization_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_6_2_1_final_holdout_target_horizon_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    protocol=J(resolve(root,a.protocol_json));feat=J(resolve(root,a.feature_authority_json));parity=J(resolve(root,a.target_adapter_parity_json))
    if protocol.get("status")!="READY" or protocol.get("final_holdout_single_use_evaluation") is not True and (protocol.get("protocol") or {}).get("final_holdout_single_use_evaluation") is not True:raise TargetError("10.7.5 protocol invalid")
    if protocol.get("final_holdout_scoring_authorized_by_this_step") is not False:raise TargetError("10.7.5 scoring boundary invalid")
    if feat.get("status")!="READY" or feat.get("final_holdout_feature_matrix_materialized") is not True:raise TargetError("10.7.6.1 feature authority invalid")
    if feat.get("final_holdout_targets_opened") is not False or feat.get("final_holdout_scoring_performed") is not False:raise TargetError("10.7.6.1 target/scoring boundary invalid")
    if parity.get("status")!="READY" or parity.get("validation_target_semantic_parity_certified") is not True:raise TargetError("10.7.6.2.0 target parity invalid")
    if parity.get("target_formula_reimplementation_performed") is not False or parity.get("final_holdout_targets_opened") is not False:raise TargetError("10.7.6.2.0 governance invalid")
    start=feat["final_holdout_start"];end=feat["final_holdout_end"];rows=int(feat["backfill_feature_row_count"]);symbols=int(feat["backfill_feature_symbol_count"])
    if start!=HOLDOUT_START:raise TargetError(f"unexpected holdout start {start}")
    outroot=resolve(root,a.output_root);outroot.mkdir(parents=True,exist_ok=True)
    raw_json=outroot.parent/"parameterized_10_6_final_holdout_report.json";raw_csv=outroot.parent/"parameterized_10_6_final_holdout_summary.csv"
    cmd=[sys.executable,str(resolve(root,a.adapter_script)),"--project-root",str(root),
         "--active-partition-label","FINAL_HOLDOUT","--partition-start",start,"--partition-end",end,
         "--expected-feature-rows",str(rows),"--expected-feature-symbols",str(symbols),
         "--validation-backfill-authority-json",a.feature_authority_json,
         "--training-gate-json",a.training_gate_json,"--development-target-authority-json",a.development_target_authority_json,
         "--development-feature-root",a.development_feature_root,"--validation-feature-root",a.final_holdout_feature_root,
         "--daily-materialization-root",a.daily_materialization_root,"--output-root",str(outroot),
         "--output-json",str(raw_json),"--output-csv",str(raw_csv)]
    print("RUN:"," ".join(cmd),flush=True)
    rc=subprocess.call(cmd,cwd=root)
    if rc!=0:raise TargetError(f"Final Holdout target adapter failed returncode={rc}")
    raw=J(raw_json)
    if raw.get("status")!="READY" or raw.get("active_partition_label")!="FINAL_HOLDOUT":raise TargetError("parameterized target report invalid")
    if raw.get("future_bars_used_for_target_labeling_only") is not True or raw.get("future_bars_used_for_feature_construction") is not False:raise TargetError("future-bar governance violated")
    scans=scan(outroot,start,end);summary={int(x["horizon"]):x for x in raw.get("target_horizon_summary") or []}
    rows_out=[]
    for h in HORIZONS:
        if h not in summary:raise TargetError(f"h{h}: summary missing")
        s=summary[h];q=scans[h]
        if q["row_count"]!=int(s["matured"]):raise TargetError(f"h{h}: matured/row count mismatch {s['matured']}/{q['row_count']}")
        if q["labels"].get("UP",0)!=int(s["UP"]) or q["labels"].get("DOWN",0)!=int(s["DOWN"]) or q["labels"].get("ZERO",0)!=int(s["ZERO"]):raise TargetError(f"h{h}: label census mismatch")
        if any(q[k] for k in ("bad_partition","bad_window","bad_horizon","bad_future_flag")):raise TargetError(f"h{h}: target contract violation {q}")
        accounted=int(s["matured"])+int(s["partition_overlap_purged"])+int(s["source_session_missing"])+int(s["symbol_target_session_missing"])
        if accounted!=rows:raise TargetError(f"h{h}: feature accounting mismatch {accounted}!={rows}")
        rows_out.append({"horizon":h,"feature_observations":rows,"matured":int(s["matured"]),"right_censored_target_session_missing":int(s["symbol_target_session_missing"]),
          "partition_overlap_purged":int(s["partition_overlap_purged"]),"source_session_missing":int(s["source_session_missing"]),
          "UP":int(s["UP"]),"DOWN":int(s["DOWN"]),"ZERO":int(s["ZERO"]),"target_file_count":q["file_count"],
          "matured_fraction":int(s["matured"])/rows})
    report={"version":"M77.19.8.7.10.7.6.2.1-FINAL-HOLDOUT-TARGET-MATERIALIZATION-AUTHORITY-1.0","status":"READY",
      "final_holdout_start":start,"final_holdout_end":end,"final_holdout_feature_observation_count":rows,"final_holdout_feature_symbol_count":symbols,
      "target_horizons":list(HORIZONS),"target_ids":["T_ABS_RET","T_REL_SPY_RET","T_DIRECTION"],"target_horizon_summary":rows_out,
      "target_semantics_source":"EXACT_10_6_PARTITION_PARAMETERIZED_ADAPTER_WITH_VALIDATION_SEMANTIC_PARITY_CERTIFIED",
      "target_formula_reimplementation_performed":False,"target_label_mapping_change_performed":False,
      "future_bars_used_for_target_labeling_only":True,"future_bars_used_for_feature_construction":False,
      "right_edge_unmatured_targets_remain_unlabeled":True,"partition_overlap_purged":True,
      "final_holdout_feature_rows_opened":True,"final_holdout_targets_opened":True,"final_holdout_targets_materialized":True,
      "final_holdout_outcomes_opened":True,"final_holdout_scoring_authorized":False,"final_holdout_scoring_performed":False,
      "validation_used_for_family_selection":False,"final_holdout_used_for_family_selection":False,
      "validation_model_refit_performed":False,"final_holdout_model_refit_performed":False,"final_holdout_preprocessor_refit_performed":False,
      "model_family_champion_selection_authorized":False,"model_family_champion_selected":False,
      "production_model_change_authorized":False,"production_authority_effect":False,
      "next_step":"BUILD_M77_19_8_7_10_7_7_FROZEN_FINAL_HOLDOUT_SCORING_EXECUTION_AUTHORITY"}
    resolve(root,a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["horizon","feature_observations","matured","right_censored_target_session_missing","partition_overlap_purged","source_session_missing","UP","DOWN","ZERO","target_file_count","matured_fraction"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows_out)
    print("=== M77.19.8.7.10.7.6.2.1 FINAL HOLDOUT TARGET MATERIALIZATION AUTHORITY ===")
    print("status: READY");print("final_holdout_start:",start);print("final_holdout_end:",end);print("final_holdout_feature_observation_count:",rows)
    for x in rows_out:
        print(f"horizon_{x['horizon']}: matured={x['matured']} right_censored={x['right_censored_target_session_missing']} purged_partition_overlap={x['partition_overlap_purged']} source_session_missing={x['source_session_missing']} labels={{'UP': {x['UP']}, 'DOWN': {x['DOWN']}, 'ZERO': {x['ZERO']}}}")
    print("target_formula_reimplementation_performed: False");print("right_edge_unmatured_targets_remain_unlabeled: True")
    print("final_holdout_targets_opened: True");print("final_holdout_outcomes_opened: True")
    print("final_holdout_scoring_authorized: False");print("final_holdout_scoring_performed: False")
    print("model_family_champion_selected: False");print("production_authority_effect: False");print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json));print("csv:",resolve(root,a.output_csv));print("target_root:",outroot)
if __name__=="__main__":main()
