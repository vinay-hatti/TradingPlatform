#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,gzip,hashlib,json,os,subprocess,tempfile,shutil
from pathlib import Path
from collections import Counter

VERSION="M77.19.8.7.10.5.2.4-EXACT-8.4.3-VALIDATION-BACKFILL-MATRIX-MATERIALIZATION-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567
REQUIRED_FEATURE_IDS=["F020","F021","F030","F031","F070","F080","F081"]

class BackfillValidationError(RuntimeError):pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp")
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def iter_rows(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise BackfillValidationError(f"{path}:{i}: invalid JSONL") from exc

def count_root(root):
    files=sorted(Path(root).glob("*.jsonl.gz"))
    rows=0
    for p in files:
        for _ in iter_rows(p):rows+=1
    return len(files),rows

# M77.19.8.7.10.5.2.4.2-CERTIFIED-8.4.3-VALIDATION-INVOCATION-BINDING-REPAIR
# M77.19.8.7.10.5.2.4.5-CERTIFIED-8.4.3-VALIDATION-ROW-ADMISSION-INVOCATION
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--validation-base-authority-json",default="reports/m77_19_8_7_10_5_2_3_5_exact_8_2_validation_routed_base_matrix_materialization.json")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_2_4_4_exact_8_4_3_partition_row_admission_parameterization_development_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_4_3_partition_row_admission_parameterized_certified.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--validation-base-root",default="research_data/m77_19_8_7_10_5_2_3_5/validation_routed_base_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_4_exact_8_4_3_validation_backfill_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_5_2_4_validation_backfill_coverage_summary.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    base_auth_path=resolve(root,args.validation_base_authority_json)
    base_auth=load_json(base_auth_path)
    adapter_auth_path=resolve(root,args.adapter_authority_json)
    adapter_auth=load_json(adapter_auth_path)
    adapter=resolve(root,args.adapter_script)

    if base_auth.get("status")!="READY" or base_auth.get("validation_base_matrix_certified") is not True:
        raise BackfillValidationError("10.5.2.3.5 Validation base matrix not READY/certified")
    if base_auth.get("validation_symbol_count")!=EXPECTED_SYMBOLS or base_auth.get("validation_row_count")!=EXPECTED_ROWS:
        raise BackfillValidationError("Validation base matrix cardinality changed")
    if base_auth.get("validation_outcomes_opened") is not False or base_auth.get("final_holdout_opened") is not False:
        raise BackfillValidationError("Validation/holdout governance violated")

    if adapter_auth.get("status")!="READY" or adapter_auth.get("development_parity_certified") is not True:
        raise BackfillValidationError("10.5.2.4.4 row-admission adapter authority not READY/certified")
    if adapter_auth.get("validation_execution_authorized") is not True:
        raise BackfillValidationError("Validation execution not authorized by 10.5.2.4.4")
    if adapter_auth.get("parameterization_scope")!="ACTIVE_PARTITION_START_END_LABEL_PLUS_EXISTING_INPUT_CARDINALITY":
        raise BackfillValidationError("unexpected 10.5.2.4.4 parameterization scope")
    if sha256_file(adapter)!=adapter_auth.get("certified_adapter_script_sha256"):
        raise BackfillValidationError("certified partition-row-admission 8.4.3 adapter SHA changed")

    base_root=resolve(root,args.validation_base_root)
    base_symbols,base_rows=count_root(base_root)
    if base_symbols!=EXPECTED_SYMBOLS or base_rows!=EXPECTED_ROWS:
        raise BackfillValidationError(f"Validation base matrix files changed: symbols={base_symbols} rows={base_rows}")

    out_root=resolve(root,args.output_root)
    if out_root.exists():shutil.rmtree(out_root)
    out_root.mkdir(parents=True,exist_ok=True)

    adapter_report=out_root.parent/"validation_backfill_adapter_report.json"
    adapter_csv=out_root.parent/"validation_backfill_adapter_coverage.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"

    # 8.4.3 partition-parameterized adapter was certified with PARTITION_END_ONLY.
    # It receives the already-isolated Validation base matrix, so its only date
    # bound is the authorized Validation end. No Development rows exist in input.
    cmd=[
        py,str(adapter),
        "--project-root",str(root),
        "--resolver-authority-json",str(resolve(root,args.resolver_authority_json)),
        "--backfill-authority-json",str(resolve(root,args.backfill_authority_json)),
        "--matrix-root",str(base_root),
        "--replay-root",str(resolve(root,args.replay_root)),
        "--daily-materialization-root",str(resolve(root,args.daily_materialization_root)),
        "--output-root",str(out_root),
        "--output-json",str(adapter_report),
        "--output-csv",str(adapter_csv),
        "--partition-end",VALIDATION_END,
        "--expected-matrix-symbol-count",str(EXPECTED_SYMBOLS),
        "--expected-matrix-row-count",str(EXPECTED_ROWS),
        "--active-partition-start",VALIDATION_START,
        "--active-partition-end",VALIDATION_END,
        "--active-partition-label","VALIDATION",
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_VALIDATION_BACKFILL_EXECUTION_FAILED",
            "validation_base_authority_sha256":sha256_file(base_auth_path),
            "adapter_authority_sha256":sha256_file(adapter_auth_path),
            "certified_adapter_script_sha256":sha256_file(adapter),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-12000:],
            "stderr_tail":proc.stderr[-12000:],
            "validation_backfill_matrix_certified":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "validation_scoring_performed":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_4_VALIDATION_BACKFILL_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,args.output_json),report)
        print("=== M77.19.8.7.10.5.2.4 EXACT 8.4.3 VALIDATION BACKFILL MATRIX MATERIALIZATION ===")
        print("status: BLOCKED_VALIDATION_BACKFILL_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("validation_backfill_matrix_certified: False")
        print("validation_targets_opened: False")
        print("validation_outcomes_opened: False")
        print("validation_scoring_performed: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,args.output_json))
        return 0

    files=sorted(out_root.glob("*.jsonl.gz"))
    symbol_count=len(files)
    row_count=0
    feature_present=Counter()
    feature_missing=Counter()
    date_window_mismatch=0
    schema=None
    schema_mismatch=0
    first_as_of=None
    last_as_of=None

    for p in files:
        for row in iter_rows(p):
            row_count+=1
            as_of=str(row.get("as_of") or "")[:10]
            if first_as_of is None or as_of<first_as_of:first_as_of=as_of
            if last_as_of is None or as_of>last_as_of:last_as_of=as_of
            if not (VALIDATION_START<=as_of<=VALIDATION_END):
                date_window_mismatch+=1
            fv=row.get("feature_values") or {}
            keys=sorted(fv.keys())
            if schema is None:schema=keys
            elif keys!=schema:schema_mismatch+=1
            for fid in REQUIRED_FEATURE_IDS:
                v=fv.get(fid)
                if v is None:
                    feature_missing[fid]+=1
                else:
                    feature_present[fid]+=1

    coverage={
        fid:{
            "present":feature_present[fid],
            "missing":feature_missing[fid],
            "coverage_pct":(feature_present[fid]/row_count if row_count else 0.0),
        }
        for fid in REQUIRED_FEATURE_IDS
    }

    full_coverage=all(
        coverage[fid]["present"]==EXPECTED_ROWS and coverage[fid]["missing"]==0
        for fid in REQUIRED_FEATURE_IDS
    )

    base_first=None
    for p in sorted(base_root.glob("*.jsonl.gz")):
        base_first=next(iter_rows(p),None)
        if base_first:break
    base_schema=sorted((base_first.get("feature_values") or {}).keys()) if base_first else []
    schema_identical=(schema==base_schema)

    certified=(
        symbol_count==EXPECTED_SYMBOLS and
        row_count==EXPECTED_ROWS and
        date_window_mismatch==0 and
        schema_mismatch==0 and
        schema_identical and
        full_coverage
    )
    status="READY" if certified else "BLOCKED_VALIDATION_BACKFILL_CERTIFICATION_FAILURE"

    report={
        "version":VERSION,
        "status":status,
        "validation_base_authority_sha256":sha256_file(base_auth_path),
        "adapter_authority_sha256":sha256_file(adapter_auth_path),
        "certified_adapter_script_sha256":sha256_file(adapter),
        "validation_symbol_count":symbol_count,
        "validation_row_count":row_count,
        "first_as_of":first_as_of,
        "last_as_of":last_as_of,
        "date_window_mismatch_row_count":date_window_mismatch,
        "validation_base_schema_column_count":len(base_schema),
        "validation_backfill_schema_column_count":len(schema or []),
        "base_backfill_schema_identical":schema_identical,
        "schema_mismatch_row_count":schema_mismatch,
        "required_feature_ids":REQUIRED_FEATURE_IDS,
        "required_feature_coverage":coverage,
        "required_features_full_coverage":full_coverage,
        "validation_backfill_matrix_certified":certified,
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_6_FROZEN_DEVELOPMENT_PREPROCESSOR_AND_VALIDATION_TARGET_MATERIALIZATION_AUTHORITY"
            if certified else
            "REVIEW_M77_19_8_7_10_5_2_4_VALIDATION_BACKFILL_CERTIFICATION_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    rows=[]
    for fid in REQUIRED_FEATURE_IDS:
        rows.append({
            "feature_id":fid,
            "present":coverage[fid]["present"],
            "missing":coverage[fid]["missing"],
            "coverage_pct":coverage[fid]["coverage_pct"],
        })
    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["feature_id","present","missing","coverage_pct"])
        w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.5.2.4 EXACT 8.4.3 VALIDATION BACKFILL MATRIX MATERIALIZATION ===")
    print("status:",status)
    print("validation_symbol_count:",symbol_count)
    print("validation_row_count:",row_count)
    print("first_as_of:",first_as_of)
    print("last_as_of:",last_as_of)
    print("date_window_mismatch_row_count:",date_window_mismatch)
    print("validation_base_schema_column_count:",len(base_schema))
    print("validation_backfill_schema_column_count:",len(schema or []))
    print("base_backfill_schema_identical:",schema_identical)
    print("schema_mismatch_row_count:",schema_mismatch)
    for fid in REQUIRED_FEATURE_IDS:
        c=coverage[fid]
        print(f"{fid}: present={c['present']} missing={c['missing']} coverage_pct={c['coverage_pct']}")
    print("required_features_full_coverage:",full_coverage)
    print("validation_backfill_matrix_certified:",certified)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    print("output_root:",out_root)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
