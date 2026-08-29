#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path

HOLDOUT_START="2023-01-01"
REQUIRED_BACKFILL=("F020","F021","F030","F031","F070","F080","F081")
class MaterializationError(RuntimeError):pass

def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def loadj(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def iter_gz(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def replay_census(replay_root):
    files=sorted((Path(replay_root)/"weekly"/"profiles").glob("*.jsonl.gz"))
    if len(files)!=602:raise MaterializationError(f"expected 602 replay profile files, found {len(files)}")
    rows=0;symbols=set();first=None;last=None
    for p in files:
        sym=p.name[:-9];n=0
        for r in iter_gz(p):
            d=str(r.get("as_of") or "")[:10]
            if d>=HOLDOUT_START and r.get("status")=="REPLAYED":
                n+=1;rows+=1;first=d if first is None or d<first else first;last=d if last is None or d>last else last
        if n:symbols.add(sym)
    if not rows or not last:raise MaterializationError("certified replay contains no Final Holdout REPLAYED observations")
    return {"symbol_count":len(symbols),"row_count":rows,"first_as_of":first,"last_as_of":last}
def matrix_scan(root):
    files=sorted(Path(root).glob("*.jsonl.gz"));rows=0;first=None;last=None;schema=None;mismatch=0
    present=Counter();missing=Counter()
    for p in files:
        for r in iter_gz(p):
            rows+=1;d=str(r.get("as_of") or "")[:10]
            first=d if first is None or d<first else first;last=d if last is None or d>last else last
            vals=r.get("feature_values") or {};keys=tuple(sorted(vals))
            if schema is None:schema=keys
            elif keys!=schema:mismatch+=1
            miss=r.get("feature_missing") or {}
            for fid in REQUIRED_BACKFILL:
                if miss.get(fid) is False and vals.get(fid) is not None:present[fid]+=1
                else:missing[fid]+=1
    return {"file_count":len(files),"row_count":rows,"first_as_of":first,"last_as_of":last,
            "schema":list(schema or []),"schema_mismatch_rows":mismatch,"present":dict(present),"missing":dict(missing)}
def run(cmd,root):
    print("RUN:", " ".join(str(x) for x in cmd),flush=True)
    rc=subprocess.call([str(x) for x in cmd],cwd=root)
    if rc!=0:raise MaterializationError(f"subprocess failed returncode={rc}: {cmd[1]}")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
    ap.add_argument("--adapter-gate-json",default="reports/m77_19_8_7_10_7_6_0_exact_final_holdout_feature_adapter_certification_gate.json")
    ap.add_argument("--continuity-gate-json",default="reports/m77_19_8_7_10_7_6_0_1_final_holdout_context_source_continuity_certification_gate.json")
    ap.add_argument("--context-adapter-script",default="scripts/run_m77_19_7_4_16_final_holdout_daily_context_continuity_certified.py")
    ap.add_argument("--base-adapter-script",default="scripts/run_m77_19_8_2_final_holdout_routing_parameterized_certified.py")
    ap.add_argument("--backfill-adapter-script",default="scripts/run_m77_19_8_4_3_final_holdout_row_admission_parameterized_certified.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--preholdout-context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_7_6_1")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_6_1_final_holdout_context_feature_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_6_1_final_holdout_feature_coverage_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    protocol=loadj(resolve(root,a.protocol_json));ag=loadj(resolve(root,a.adapter_gate_json));cg=loadj(resolve(root,a.continuity_gate_json))
    if protocol.get("status")!="READY" or protocol.get("final_holdout_feature_materialization_authorized") is not True:raise MaterializationError("10.7.5 protocol invalid")
    if protocol.get("final_holdout_scoring_authorized_by_this_step") is not False or protocol.get("final_holdout_opened") is not False:raise MaterializationError("10.7.5 holdout/scoring boundary invalid")
    if ag.get("status")!="READY" or not all(ag.get(k) is True for k in ("context_adapter_certified","base_matrix_adapter_certified","backfill_adapter_certified")):raise MaterializationError("10.7.6.0 adapter gate invalid")
    if cg.get("status")!="READY" or cg.get("frozen_daily_spy_close_parity_certified") is not True or cg.get("rolling_4w_13w_26w_52w_continuity_certified") is not True:raise MaterializationError("10.7.6.0.1 continuity gate invalid")
    if cg.get("outcome_authority_required_for_final_holdout_context") is not False:raise MaterializationError("context still requires outcome authority")

    census=replay_census(resolve(root,a.replay_root));end=census["last_as_of"]
    outroot=resolve(root,a.output_root);ctx_csv=outroot/"final_holdout_context.csv";ctx_json=outroot/"final_holdout_context.json"
    base_root=outroot/"final_holdout_base_feature_matrix";base_json=outroot/"final_holdout_base_feature_matrix.json";base_csv=outroot/"final_holdout_base_feature_schema.csv"
    back_root=outroot/"final_holdout_feature_matrix_certified_backfill";back_json=outroot/"final_holdout_backfill.json";back_csv=outroot/"final_holdout_backfill_coverage.csv"
    outroot.mkdir(parents=True,exist_ok=True)

    run([sys.executable,resolve(root,a.context_adapter_script),"--project-root",root,
         "--replay-authority-json",a.replay_authority_json,"--resolver-authority-json",a.resolver_authority_json,
         "--replay-root",a.replay_root,"--daily-materialization-root",a.daily_materialization_root,
         "--preholdout-context-csv",a.preholdout_context_csv,"--partition-start",HOLDOUT_START,"--partition-end",end,
         "--output-json",ctx_json,"--output-csv",ctx_csv],root)
    ctx=loadj(ctx_json)
    if ctx.get("status")!="READY" or ctx.get("outcome_authority_read") is not False:raise MaterializationError("Final Holdout context certification failed")

    run([sys.executable,resolve(root,a.base_adapter_script),"--project-root",root,
         "--partition-start",HOLDOUT_START,"--partition-end",end,"--partition-label","FINAL_HOLDOUT",
         "--feature-authority-json",a.feature_authority_json,"--replay-authority-json",a.replay_authority_json,
         "--replay-root",a.replay_root,"--context-csv",ctx_csv,"--output-root",base_root,
         "--output-json",base_json,"--output-csv",base_csv],root)
    base=matrix_scan(base_root)
    if base["row_count"]!=census["row_count"] or base["file_count"]!=census["symbol_count"]:raise MaterializationError(f"base cardinality mismatch replay={census} base={base}")
    if base["first_as_of"]!=census["first_as_of"] or base["last_as_of"]!=census["last_as_of"] or base["schema_mismatch_rows"]!=0:raise MaterializationError("base observation/schema boundary mismatch")

    run([sys.executable,resolve(root,a.backfill_adapter_script),"--project-root",root,
         "--active-partition-start",HOLDOUT_START,"--active-partition-end",end,"--active-partition-label","FINAL_HOLDOUT",
         "--expected-matrix-symbol-count",str(census["symbol_count"]),"--expected-matrix-row-count",str(census["row_count"]),
         "--partition-end",end,"--resolver-authority-json",a.resolver_authority_json,"--backfill-authority-json",a.backfill_authority_json,
         "--matrix-root",base_root,"--replay-root",a.replay_root,"--daily-materialization-root",a.daily_materialization_root,
         "--output-root",back_root,"--output-json",back_json,"--output-csv",back_csv],root)
    back=matrix_scan(back_root)
    if back["row_count"]!=census["row_count"] or back["file_count"]!=census["symbol_count"] or back["schema_mismatch_rows"]!=0:raise MaterializationError("backfill cardinality/schema mismatch")
    if base["schema"]!=back["schema"]:raise MaterializationError("base/backfill feature schema changed")

    val=matrix_scan(resolve(root,a.validation_feature_root))
    if val["schema"]!=back["schema"]:raise MaterializationError("Validation/Final Holdout 27-feature schema mismatch")
    full=True
    for fid in REQUIRED_BACKFILL:
        if back["missing"].get(fid,0)!=0 or back["present"].get(fid,0)!=census["row_count"]:full=False
    if not full:raise MaterializationError(f"required Final Holdout backfill coverage incomplete: {back['present']} {back['missing']}")

    report={"version":"M77.19.8.7.10.7.6.1-FINAL-HOLDOUT-CONTEXT-FEATURE-MATRIX-MATERIALIZATION-1.0","status":"READY",
      "final_holdout_start":HOLDOUT_START,"final_holdout_end":end,
      "expected_replay_symbol_count":census["symbol_count"],"expected_replay_row_count":census["row_count"],
      "expected_first_as_of":census["first_as_of"],"expected_last_as_of":census["last_as_of"],
      "context_row_count":ctx["row_count"],"context_first_as_of":ctx["first_as_of"],"context_last_as_of":ctx["last_as_of"],
      "context_outcome_authority_read":False,"base_feature_symbol_count":base["file_count"],"base_feature_row_count":base["row_count"],
      "backfill_feature_symbol_count":back["file_count"],"backfill_feature_row_count":back["row_count"],
      "feature_schema_column_count":len(back["schema"]),"validation_final_holdout_schema_identical":True,
      "required_backfill_features_full_coverage":True,
      "coverage":{fid:{"present":back["present"].get(fid,0),"missing":back["missing"].get(fid,0),"coverage_pct":back["present"].get(fid,0)/census["row_count"]} for fid in REQUIRED_BACKFILL},
      "final_holdout_context_opened":True,"final_holdout_feature_rows_opened":True,"final_holdout_feature_matrix_materialized":True,
      "final_holdout_targets_opened":False,"final_holdout_outcomes_opened":False,"final_holdout_scoring_performed":False,
      "validation_used_for_selection":False,"model_family_champion_selected":False,"production_authority_effect":False,
      "next_step":"BUILD_M77_19_8_7_10_7_6_2_FINAL_HOLDOUT_TARGET_MATERIALIZATION_AUTHORITY"}
    resolve(root,a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["feature_id","present","missing","coverage_pct"];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for fid in REQUIRED_BACKFILL:w.writerow({"feature_id":fid,**report["coverage"][fid]})
    print("=== M77.19.8.7.10.7.6.1 FINAL HOLDOUT CONTEXT & FEATURE MATRIX MATERIALIZATION ===")
    print("status: READY");print("final_holdout_start:",HOLDOUT_START);print("final_holdout_end:",end)
    print("final_holdout_symbol_count:",census["symbol_count"]);print("final_holdout_row_count:",census["row_count"])
    print("first_as_of:",census["first_as_of"]);print("last_as_of:",census["last_as_of"])
    print("context_outcome_authority_read: False");print("feature_schema_column_count:",len(back["schema"]))
    print("validation_final_holdout_schema_identical: True")
    for fid in REQUIRED_BACKFILL:print(f"{fid}: present={back['present'].get(fid,0)} missing={back['missing'].get(fid,0)} coverage_pct={report['coverage'][fid]['coverage_pct']}")
    print("required_backfill_features_full_coverage: True")
    print("final_holdout_context_opened: True");print("final_holdout_feature_rows_opened: True");print("final_holdout_feature_matrix_materialized: True")
    print("final_holdout_targets_opened: False");print("final_holdout_outcomes_opened: False");print("final_holdout_scoring_performed: False")
    print("model_family_champion_selected: False");print("production_authority_effect: False");print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json));print("csv:",resolve(root,a.output_csv));print("output_root:",outroot)
if __name__=="__main__":main()
