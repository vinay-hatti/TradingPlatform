#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,gzip,hashlib,json,os,subprocess,tempfile,shutil
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.3.3-EXACT-8.2-VALIDATION-PARTITION-BASE-MATRIX-MATERIALIZATION-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
VALIDATION_PARTITION="VALIDATION"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567

class ValidationBaseMatrixError(RuntimeError):pass

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
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
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
            except Exception as exc:raise ValidationBaseMatrixError(f"{path}:{i}: invalid JSONL") from exc

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_2_3_2_exact_8_2_partition_label_and_end_parameterization_development_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_2_partition_label_end_parameterized_certified.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--development-base-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_5_2_3_3/validation_partition_base_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_3_3_exact_8_2_validation_partition_base_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_5_2_3_3_validation_partition_base_matrix_schema_summary.csv")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    auth_path=resolve(root,a.adapter_authority_json)
    auth=load_json(auth_path)
    adapter=resolve(root,a.adapter_script)

    if auth.get("status")!="READY" or auth.get("adapter_development_parity_certified") is not True:
        raise ValidationBaseMatrixError("10.5.2.3.2 adapter authority not READY/certified")
    if auth.get("validation_base_matrix_execution_authorized") is not True:
        raise ValidationBaseMatrixError("Validation base matrix execution not authorized")
    if auth.get("parameterization_scope")!="PARTITION_END_AND_PARTITION_LABEL_ONLY":
        raise ValidationBaseMatrixError("unexpected certified parameterization scope")
    if auth.get("validation_outcomes_opened") is not False or auth.get("final_holdout_opened") is not False:
        raise ValidationBaseMatrixError("partition governance violated")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ValidationBaseMatrixError("certified adapter SHA changed")

    out_root=resolve(root,a.output_root)
    if out_root.exists():shutil.rmtree(out_root)
    out_root.mkdir(parents=True,exist_ok=True)

    tmp_json=out_root.parent/"validation_partition_adapter_report.json"
    tmp_csv=out_root.parent/"validation_partition_adapter_schema.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter),
        "--project-root",str(root),
        "--feature-authority-json",str(resolve(root,a.feature_authority_json)),
        "--replay-authority-json",str(resolve(root,a.replay_authority_json)),
        "--replay-root",str(resolve(root,a.replay_root)),
        "--context-csv",str(resolve(root,a.context_csv)),
        "--output-root",str(out_root),
        "--output-json",str(tmp_json),
        "--output-csv",str(tmp_csv),
        "--partition-end",VALIDATION_END,
        "--partition-label",VALIDATION_PARTITION,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_VALIDATION_PARTITION_BASE_MATRIX_EXECUTION_FAILED",
            "adapter_authority_sha256":sha256_file(auth_path),
            "certified_adapter_script_sha256":sha256_file(adapter),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "validation_base_matrix_certified":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "validation_scoring_performed":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_3_3_VALIDATION_PARTITION_BASE_MATRIX_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,a.output_json),report)
        print("=== M77.19.8.7.10.5.2.3.3 EXACT 8.2 VALIDATION-PARTITION BASE-MATRIX MATERIALIZATION ===")
        print("status: BLOCKED_VALIDATION_PARTITION_BASE_MATRIX_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("validation_base_matrix_certified: False")
        print("validation_targets_opened: False")
        print("validation_outcomes_opened: False")
        print("validation_scoring_performed: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,a.output_json))
        return 0

    files=sorted(out_root.glob("*.jsonl.gz"))
    symbol_count=len(files)
    row_count=0
    schema=None
    schema_mismatch=0
    partition_mismatch=0
    date_window_mismatch=0
    first_as_of=None
    last_as_of=None

    for p in files:
        for row in iter_rows(p):
            row_count+=1
            as_of=str(row.get("as_of") or "")[:10]
            if first_as_of is None or as_of<first_as_of:first_as_of=as_of
            if last_as_of is None or as_of>last_as_of:last_as_of=as_of
            if row.get("partition")!=VALIDATION_PARTITION:partition_mismatch+=1
            if not (VALIDATION_START<=as_of<=VALIDATION_END):date_window_mismatch+=1
            fv=row.get("feature_values") or {}
            keys=sorted(fv.keys())
            if schema is None:schema=keys
            elif keys!=schema:schema_mismatch+=1

    dev_root=resolve(root,a.development_base_root)
    dev_first=None
    for p in sorted(dev_root.glob("*.jsonl.gz")):
        dev_first=next(iter_rows(p),None)
        if dev_first:break
    dev_schema=sorted((dev_first.get("feature_values") or {}).keys()) if dev_first else []
    schema_identical=(schema==dev_schema)

    certified=(
        symbol_count==EXPECTED_SYMBOLS and
        row_count==EXPECTED_ROWS and
        first_as_of>=VALIDATION_START and
        last_as_of<=VALIDATION_END and
        partition_mismatch==0 and
        date_window_mismatch==0 and
        schema_mismatch==0 and
        schema_identical
    )
    status="READY" if certified else "BLOCKED_VALIDATION_PARTITION_BASE_MATRIX_CERTIFICATION_FAILURE"

    report={
        "version":VERSION,
        "status":status,
        "adapter_authority_sha256":sha256_file(auth_path),
        "certified_adapter_script_sha256":sha256_file(adapter),
        "validation_partition_label":VALIDATION_PARTITION,
        "validation_partition_end":VALIDATION_END,
        "validation_symbol_count":symbol_count,
        "validation_row_count":row_count,
        "first_as_of":first_as_of,
        "last_as_of":last_as_of,
        "partition_mismatch_row_count":partition_mismatch,
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
            "REVIEW_M77_19_8_7_10_5_2_3_3_VALIDATION_PARTITION_BASE_MATRIX_CERTIFICATION_FAILURE"
        ),
    }
    atomic_json(resolve(root,a.output_json),report)

    rows=[
        {"metric":"validation_symbol_count","value":symbol_count},
        {"metric":"validation_row_count","value":row_count},
        {"metric":"partition_mismatch_row_count","value":partition_mismatch},
        {"metric":"date_window_mismatch_row_count","value":date_window_mismatch},
        {"metric":"validation_schema_mismatch_row_count","value":schema_mismatch},
        {"metric":"development_validation_schema_identical","value":schema_identical},
    ]
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["metric","value"])
        w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.5.2.3.3 EXACT 8.2 VALIDATION-PARTITION BASE-MATRIX MATERIALIZATION ===")
    print("status:",status)
    print("validation_partition_label:",VALIDATION_PARTITION)
    print("validation_partition_end:",VALIDATION_END)
    print("validation_symbol_count:",symbol_count)
    print("validation_row_count:",row_count)
    print("first_as_of:",first_as_of)
    print("last_as_of:",last_as_of)
    print("partition_mismatch_row_count:",partition_mismatch)
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
    print("report:",resolve(root,a.output_json))
    print("csv:",resolve(root,a.output_csv))
    print("output_root:",out_root)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
