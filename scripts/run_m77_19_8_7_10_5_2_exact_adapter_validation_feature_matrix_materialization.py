#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,subprocess,tempfile,shutil
from pathlib import Path

VERSION="M77.19.8.7.10.5.2-EXACT-ADAPTER-VALIDATION-FEATURE-MATRIX-MATERIALIZATION-1.0"
VALIDATION_END="2022-12-31"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")

class ValidationError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser(); return p.resolve() if p.is_absolute() else (root/p).resolve()
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def iter_rows(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except Exception as exc: raise ValidationError(f"{path}:{i}: invalid JSONL") from exc

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_1_exact_8_4_3_partition_parameterization_adapter_development_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_4_3_partition_parameterized_certified.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_5_2/validation_feature_matrix_certified")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_exact_adapter_validation_feature_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_5_2_validation_feature_coverage_summary.csv")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    auth_path=resolve(root,a.adapter_authority_json)
    auth=load_json(auth_path)
    adapter=resolve(root,a.adapter_script)

    if auth.get("status")!="READY" or auth.get("adapter_development_parity_certified") is not True:
        raise ValidationError("10.5.1 adapter authority not READY/certified")
    if auth.get("validation_execution_authorized") is not True:
        raise ValidationError("Validation execution not authorized")
    if auth.get("validation_outcomes_opened") is not False or auth.get("final_holdout_opened") is not False:
        raise ValidationError("partition governance violated")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ValidationError("certified adapter SHA changed")

    out_root=resolve(root,a.output_root)
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True,exist_ok=True)

    tmp_json=out_root.parent/"validation_adapter_report.json"
    tmp_csv=out_root.parent/"validation_adapter_coverage.csv"
    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"

    cmd=[
        py,str(adapter),
        "--project-root",str(root),
        "--resolver-authority-json",str(resolve(root,a.resolver_authority_json)),
        "--backfill-authority-json",str(resolve(root,a.backfill_authority_json)),
        "--matrix-root",str(resolve(root,a.matrix_root)),
        "--replay-root",str(resolve(root,a.replay_root)),
        "--daily-materialization-root",str(resolve(root,a.daily_materialization_root)),
        "--output-root",str(out_root),
        "--output-json",str(tmp_json),
        "--output-csv",str(tmp_csv),
        "--partition-end",VALIDATION_END,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_VALIDATION_ADAPTER_EXECUTION_FAILED",
            "adapter_authority_sha256":sha256_file(auth_path),
            "certified_adapter_script_sha256":sha256_file(adapter),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "validation_feature_matrix_certified":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "validation_scoring_performed":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_VALIDATION_ADAPTER_EXECUTION_FAILURE"
        }
        atomic_json(resolve(root,a.output_json),report)
        print("=== M77.19.8.7.10.5.2 EXACT ADAPTER VALIDATION FEATURE MATRIX MATERIALIZATION ===")
        print("status: BLOCKED_VALIDATION_ADAPTER_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("validation_feature_matrix_certified: False")
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
    cov={fid:{"present":0,"missing":0} for fid in REQUIRED_FEATURE_IDS}

    for p in files:
        for row in iter_rows(p):
            row_count+=1
            fv=row.get("feature_values") or {}
            keys=sorted(fv.keys())
            if schema is None:
                schema=keys
            elif keys!=schema:
                schema_mismatch+=1
            for fid in REQUIRED_FEATURE_IDS:
                if fv.get(fid) is None:
                    cov[fid]["missing"]+=1
                else:
                    cov[fid]["present"]+=1

    dev_root=resolve(root,a.development_feature_root)
    dev_first=None
    for p in sorted(dev_root.glob("*.jsonl.gz")):
        dev_first=next(iter_rows(p),None)
        if dev_first:
            break
    dev_schema=sorted((dev_first.get("feature_values") or {}).keys()) if dev_first else []
    schema_identical=(schema==dev_schema)

    coverage=[]
    for fid in REQUIRED_FEATURE_IDS:
        p=cov[fid]["present"];m=cov[fid]["missing"];den=p+m
        coverage.append({"feature_id":fid,"present":p,"missing":m,"coverage_pct":p/den if den else None})

    coverage_ok=all(x["present"]==EXPECTED_ROWS and x["missing"]==0 for x in coverage)
    certified=(
        symbol_count==EXPECTED_SYMBOLS and
        row_count==EXPECTED_ROWS and
        schema_mismatch==0 and
        schema_identical and
        coverage_ok
    )

    status="READY" if certified else "BLOCKED_VALIDATION_FEATURE_MATRIX_CERTIFICATION_FAILURE"
    report={
        "version":VERSION,
        "status":status,
        "adapter_authority_sha256":sha256_file(auth_path),
        "certified_adapter_script_sha256":sha256_file(adapter),
        "validation_partition_end":VALIDATION_END,
        "validation_symbol_count":symbol_count,
        "validation_row_count":row_count,
        "development_feature_schema_column_count":len(dev_schema),
        "validation_feature_schema_column_count":len(schema or []),
        "validation_schema_mismatch_row_count":schema_mismatch,
        "development_validation_schema_identical":schema_identical,
        "required_feature_coverage":coverage,
        "validation_feature_matrix_certified":certified,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_6_FROZEN_DEVELOPMENT_PREPROCESSOR_AND_VALIDATION_TARGET_MATERIALIZATION_AUTHORITY"
            if certified else
            "REVIEW_M77_19_8_7_10_5_2_VALIDATION_FEATURE_MATRIX_CERTIFICATION_FAILURE"
        )
    }
    atomic_json(resolve(root,a.output_json),report)

    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(coverage[0]))
        w.writeheader()
        w.writerows(coverage)

    print("=== M77.19.8.7.10.5.2 EXACT ADAPTER VALIDATION FEATURE MATRIX MATERIALIZATION ===")
    print("status:",status)
    print("validation_symbol_count:",symbol_count)
    print("validation_row_count:",row_count)
    print("development_feature_schema_column_count:",len(dev_schema))
    print("validation_feature_schema_column_count:",len(schema or []))
    print("development_validation_schema_identical:",schema_identical)
    print("validation_schema_mismatch_row_count:",schema_mismatch)
    for x in coverage:
        print(f"{x['feature_id']}: present={x['present']} missing={x['missing']} coverage_pct={x['coverage_pct']}")
    print("validation_feature_matrix_certified:",certified)
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
