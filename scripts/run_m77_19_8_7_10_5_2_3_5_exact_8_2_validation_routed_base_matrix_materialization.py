#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,gzip,hashlib,json,os,subprocess,tempfile,shutil
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.3.5-EXACT-8.2-VALIDATION-ROUTED-BASE-MATRIX-MATERIALIZATION-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
VALIDATION_PARTITION="VALIDATION"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567

class ValidationMatrixError(RuntimeError):pass

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
            except Exception as exc:raise ValidationMatrixError(f"{path}:{i}: invalid JSONL") from exc

# M77.19.8.7.10.5.2.3.5.1-OUTPUT-SCHEMA-AWARE-VALIDATION-PARTITION-CERTIFICATION-REPAIR
# M77.19.8.7.10.5.2.3.5.2-REPLAY-DERIVED-VALIDATION-OBSERVATION-BOUNDARY-CERTIFICATION-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--routing-authority-json",default="reports/m77_19_8_7_10_5_2_3_4_exact_8_2_partition_routing_parameterization_development_parity_gate.json")
    ap.add_argument("--routing-adapter-script",default="scripts/run_m77_19_8_2_partition_routing_parameterized_certified.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--development-base-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_5_2_3_5/validation_routed_base_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_3_5_exact_8_2_validation_routed_base_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_5_2_3_5_validation_routed_base_matrix_schema_summary.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    auth_path=resolve(root,args.routing_authority_json)
    auth=load_json(auth_path)
    adapter=resolve(root,args.routing_adapter_script)

    if auth.get("status")!="READY" or auth.get("adapter_development_parity_certified") is not True:
        raise ValidationMatrixError("10.5.2.3.4 routing authority not READY/certified")
    if auth.get("validation_base_matrix_execution_authorized") is not True:
        raise ValidationMatrixError("Validation base matrix execution not authorized")
    if auth.get("parameterization_scope")!="PARTITION_ROUTING_START_END_LABEL_ONLY":
        raise ValidationMatrixError("unexpected routing scope")
    if auth.get("final_holdout_skip_unconditional") is not True:
        raise ValidationMatrixError("Final Holdout unconditional skip not certified")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ValidationMatrixError("certified routing adapter SHA changed")

    out_root=resolve(root,args.output_root)
    if out_root.exists():shutil.rmtree(out_root)
    out_root.mkdir(parents=True,exist_ok=True)

    tmp_json=out_root.parent/"validation_routing_adapter_report.json"
    tmp_csv=out_root.parent/"validation_routing_adapter_schema.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter),
        "--project-root",str(root),
        "--feature-authority-json",str(resolve(root,args.feature_authority_json)),
        "--replay-authority-json",str(resolve(root,args.replay_authority_json)),
        "--replay-root",str(resolve(root,args.replay_root)),
        "--context-csv",str(resolve(root,args.context_csv)),
        "--output-root",str(out_root),
        "--output-json",str(tmp_json),
        "--output-csv",str(tmp_csv),
        "--partition-start",VALIDATION_START,
        "--partition-end",VALIDATION_END,
        "--partition-label",VALIDATION_PARTITION,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_VALIDATION_ROUTED_BASE_MATRIX_EXECUTION_FAILED",
            "routing_authority_sha256":sha256_file(auth_path),
            "certified_routing_adapter_sha256":sha256_file(adapter),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "validation_base_matrix_certified":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "validation_scoring_performed":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_3_5_VALIDATION_ROUTING_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,args.output_json),report)
        print("=== M77.19.8.7.10.5.2.3.5 EXACT 8.2 VALIDATION-ROUTED BASE-MATRIX MATERIALIZATION ===")
        print("status: BLOCKED_VALIDATION_ROUTED_BASE_MATRIX_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("validation_base_matrix_certified: False")
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
    schema=None
    schema_mismatch=0
    # M77.19.8.7.10.5.2.3.5.1:
    # Frozen 8.2 rows do not emit a `partition` column. Certify partition
    # membership from the SHA-pinned routing authority + explicit route/window.
    partition_metadata_field_present_count=0
    unexpected_partition_metadata_value_count=0
    date_window_mismatch=0
    first_as_of=None
    last_as_of=None

    for p in files:
        for row in iter_rows(p):
            row_count+=1
            as_of=str(row.get("as_of") or "")[:10]
            if first_as_of is None or as_of<first_as_of:first_as_of=as_of
            if last_as_of is None or as_of>last_as_of:last_as_of=as_of
            if "partition" in row:
                partition_metadata_field_present_count+=1
                if row.get("partition")!=VALIDATION_PARTITION:
                    unexpected_partition_metadata_value_count+=1
            if not (VALIDATION_START<=as_of<=VALIDATION_END):date_window_mismatch+=1
            fv=row.get("feature_values") or {}
            keys=sorted(fv.keys())
            if schema is None:schema=keys
            elif keys!=schema:schema_mismatch+=1

    dev_root=resolve(root,args.development_base_root)
    dev_first=None
    for p in sorted(dev_root.glob("*.jsonl.gz")):
        dev_first=next(iter_rows(p),None)
        if dev_first:break
    dev_schema=sorted((dev_first.get("feature_values") or {}).keys()) if dev_first else []
    schema_identical=(schema==dev_schema)

    # M77.19.8.7.10.5.2.3.5.2:
    # Calendar partition bounds are not guaranteed observation dates.
    # Independently derive expected Validation observation boundaries and
    # cardinality from frozen REPLAYED rows within the authorized window.
    replay_profiles=resolve(root,args.replay_root)/"weekly"/"profiles"
    expected_validation_first_as_of=None
    expected_validation_last_as_of=None
    expected_validation_replay_row_count=0
    expected_validation_replay_symbol_count=0

    for replay_path in sorted(replay_profiles.glob("*.jsonl.gz")):
        symbol_has_validation=False
        for replay_row in iter_rows(replay_path):
            replay_as_of=str(replay_row.get("as_of") or "")[:10]
            if replay_row.get("status")!="REPLAYED":
                continue
            if VALIDATION_START<=replay_as_of<=VALIDATION_END:
                symbol_has_validation=True
                expected_validation_replay_row_count+=1
                if expected_validation_first_as_of is None or replay_as_of<expected_validation_first_as_of:
                    expected_validation_first_as_of=replay_as_of
                if expected_validation_last_as_of is None or replay_as_of>expected_validation_last_as_of:
                    expected_validation_last_as_of=replay_as_of
        if symbol_has_validation:
            expected_validation_replay_symbol_count+=1

    certified=(
        symbol_count==EXPECTED_SYMBOLS and
        row_count==EXPECTED_ROWS and
        expected_validation_replay_symbol_count==EXPECTED_SYMBOLS and
        expected_validation_replay_row_count==EXPECTED_ROWS and
        first_as_of==expected_validation_first_as_of and
        last_as_of==expected_validation_last_as_of and
        unexpected_partition_metadata_value_count==0 and
        date_window_mismatch==0 and
        schema_mismatch==0 and
        schema_identical
    )
    status="READY" if certified else "BLOCKED_VALIDATION_ROUTED_BASE_MATRIX_CERTIFICATION_FAILURE"

    report={
        "version":VERSION,
        "status":status,
        "routing_authority_sha256":sha256_file(auth_path),
        "certified_routing_adapter_sha256":sha256_file(adapter),
        "validation_partition_start":VALIDATION_START,
        "validation_partition_end":VALIDATION_END,
        "validation_partition_label":VALIDATION_PARTITION,
        "validation_symbol_count":symbol_count,
        "validation_row_count":row_count,
        "first_as_of":first_as_of,
        "last_as_of":last_as_of,
        "expected_validation_replay_symbol_count":expected_validation_replay_symbol_count,
        "expected_validation_replay_row_count":expected_validation_replay_row_count,
        "expected_validation_first_as_of":expected_validation_first_as_of,
        "expected_validation_last_as_of":expected_validation_last_as_of,
        "observation_boundary_certification_method":"FROZEN_REPLAY_REPLAYED_ROWS_WITHIN_AUTHORIZED_VALIDATION_WINDOW",
        "partition_certification_method":"SHA_PINNED_ROUTING_AUTHORITY_PLUS_EXPLICIT_VALIDATION_ROUTE_AND_DATE_WINDOW",
        "output_partition_metadata_required":False,
        "partition_metadata_field_present_count":partition_metadata_field_present_count,
        "unexpected_partition_metadata_value_count":unexpected_partition_metadata_value_count,
        "date_window_mismatch_row_count":date_window_mismatch,
        "development_feature_schema_column_count":len(dev_schema),
        "validation_feature_schema_column_count":len(schema or []),
        "development_validation_schema_identical":schema_identical,
        "validation_schema_mismatch_row_count":schema_mismatch,
        "validation_base_matrix_certified":certified,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_4_EXACT_8_4_3_VALIDATION_BACKFILL_MATRIX_MATERIALIZATION"
            if certified else
            "REVIEW_M77_19_8_7_10_5_2_3_5_VALIDATION_ROUTED_BASE_MATRIX_CERTIFICATION_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    rows=[
        {"metric":"validation_symbol_count","value":symbol_count},
        {"metric":"validation_row_count","value":row_count},
        {"metric":"first_as_of","value":first_as_of},
        {"metric":"last_as_of","value":last_as_of},
        {"metric":"expected_validation_replay_symbol_count","value":expected_validation_replay_symbol_count},
        {"metric":"expected_validation_replay_row_count","value":expected_validation_replay_row_count},
        {"metric":"expected_validation_first_as_of","value":expected_validation_first_as_of},
        {"metric":"expected_validation_last_as_of","value":expected_validation_last_as_of},
        {"metric":"observation_boundary_certification_method","value":"FROZEN_REPLAY_REPLAYED_ROWS_WITHIN_AUTHORIZED_VALIDATION_WINDOW"},
        {"metric":"partition_certification_method","value":"SHA_PINNED_ROUTING_AUTHORITY_PLUS_EXPLICIT_VALIDATION_ROUTE_AND_DATE_WINDOW"},
        {"metric":"output_partition_metadata_required","value":False},
        {"metric":"partition_metadata_field_present_count","value":partition_metadata_field_present_count},
        {"metric":"unexpected_partition_metadata_value_count","value":unexpected_partition_metadata_value_count},
        {"metric":"date_window_mismatch_row_count","value":date_window_mismatch},
        {"metric":"development_validation_schema_identical","value":schema_identical},
        {"metric":"validation_schema_mismatch_row_count","value":schema_mismatch},
    ]
    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["metric","value"]);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.5.2.3.5 EXACT 8.2 VALIDATION-ROUTED BASE-MATRIX MATERIALIZATION ===")
    print("status:",status)
    print("validation_partition_start:",VALIDATION_START)
    print("validation_partition_end:",VALIDATION_END)
    print("validation_partition_label:",VALIDATION_PARTITION)
    print("validation_symbol_count:",symbol_count)
    print("validation_row_count:",row_count)
    print("first_as_of:",first_as_of)
    print("last_as_of:",last_as_of)
    print("expected_validation_replay_symbol_count:",expected_validation_replay_symbol_count)
    print("expected_validation_replay_row_count:",expected_validation_replay_row_count)
    print("expected_validation_first_as_of:",expected_validation_first_as_of)
    print("expected_validation_last_as_of:",expected_validation_last_as_of)
    print("observation_boundary_certification_method: FROZEN_REPLAY_REPLAYED_ROWS_WITHIN_AUTHORIZED_VALIDATION_WINDOW")
    print("partition_certification_method: SHA_PINNED_ROUTING_AUTHORITY_PLUS_EXPLICIT_VALIDATION_ROUTE_AND_DATE_WINDOW")
    print("output_partition_metadata_required: False")
    print("partition_metadata_field_present_count:",partition_metadata_field_present_count)
    print("unexpected_partition_metadata_value_count:",unexpected_partition_metadata_value_count)
    print("date_window_mismatch_row_count:",date_window_mismatch)
    print("development_feature_schema_column_count:",len(dev_schema))
    print("validation_feature_schema_column_count:",len(schema or []))
    print("development_validation_schema_identical:",schema_identical)
    print("validation_schema_mismatch_row_count:",schema_mismatch)
    print("validation_base_matrix_certified:",certified)
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
