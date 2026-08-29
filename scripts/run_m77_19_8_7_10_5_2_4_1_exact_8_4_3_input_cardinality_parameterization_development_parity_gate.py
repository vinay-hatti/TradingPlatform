#!/usr/bin/env python3
from __future__ import annotations

import argparse,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.4.1-EXACT-8.4.3-INPUT-CARDINALITY-PARAMETERIZATION-DEVELOPMENT-PARITY-GATE-1.0"
DEV_SYMBOLS=524
DEV_ROWS=303689
DEV_END="2017-12-31"

class GateError(RuntimeError):
    pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp")
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True)
            f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def iter_rows(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except Exception as exc:
                raise GateError(f"{path}:{i}: invalid JSONL") from exc

def row_hash(row):
    return hashlib.sha256(
        json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    ).hexdigest()

def compare_dirs(expected_root,actual_root):
    exp={p.name:p for p in Path(expected_root).glob("*.jsonl.gz")}
    act={p.name:p for p in Path(actual_root).glob("*.jsonl.gz")}
    missing=sorted(set(exp)-set(act))
    extra=sorted(set(act)-set(exp))
    mismatch=[]
    erows=0
    arows=0
    for name in sorted(set(exp)&set(act)):
        e=list(iter_rows(exp[name]))
        a=list(iter_rows(act[name]))
        erows+=len(e)
        arows+=len(a)
        if len(e)!=len(a) or any(row_hash(x)!=row_hash(y) for x,y in zip(e,a)):
            mismatch.append(name[:-9])
    return len(exp),len(act),erows,arows,missing,extra,mismatch

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-validation-json",default="reports/m77_19_8_7_10_5_2_4_exact_8_4_3_validation_backfill_matrix_materialization.json")
    ap.add_argument("--source-adapter-script",default="scripts/run_m77_19_8_4_3_partition_parameterized_certified.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--development-matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--certified-development-backfill-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_4_1_exact_8_4_3_input_cardinality_parameterization_development_parity_gate.json")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    failed=load_json(resolve(root,args.failed_validation_json))
    source=resolve(root,args.source_adapter_script)

    if failed.get("status")!="BLOCKED_VALIDATION_BACKFILL_EXECUTION_FAILED":
        raise GateError("10.5.2.4 not in expected blocked state")
    stderr=failed.get("stderr_tail") or ""
    if "expected 524 Development matrix files, found 570" not in stderr:
        raise GateError("10.5.2.4 failure mode changed")
    if failed.get("validation_outcomes_opened") is not False or failed.get("final_holdout_opened") is not False:
        raise GateError("governance violation")

    text=source.read_text(encoding="utf-8")

    old_guard = '    if len(matrix_files)!=524:raise RepairError(f"expected 524 Development matrix files, found {len(matrix_files)}")'
    if old_guard not in text:
        raise GateError("canonical 524-file guard not found")

    parser_anchor='ap=argparse.ArgumentParser()'
    if parser_anchor not in text:
        raise GateError("ArgumentParser anchor missing")
    text=text.replace(
        parser_anchor,
        parser_anchor+
        '\n    ap.add_argument("--expected-matrix-symbol-count",type=int,default=524)'+
        '\n    ap.add_argument("--expected-matrix-row-count",type=int,default=303689)',
        1
    )

    new_guard = (
        '    if len(matrix_files)!=args.expected_matrix_symbol_count:\n'
        '        raise RepairError(f"expected {args.expected_matrix_symbol_count} matrix files, found {len(matrix_files)}")'
    )
    text=text.replace(old_guard,new_guard,1)

    replacements=0
    row_patterns=[
        'if total_rows!=303689:',
        'if materialized_row_count!=303689:',
        'if total_rows != 303689:',
        'if materialized_row_count != 303689:',
    ]
    for pat in row_patterns:
        if pat in text:
            lhs=pat.split("!=")[0].strip().replace("if ","")
            text=text.replace(pat,f"if {lhs}!=args.expected_matrix_row_count:",1)
            replacements+=1

    compile(text,"<m77_19_8_7_10_5_2_4_1_adapter>","exec")

    work=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_2_4_1_",dir=str(root/"research_data")))
    adapter=work/"run_m77_19_8_4_3_cardinality_parameterized.py"
    adapter.write_text(text,encoding="utf-8")

    out_root=work/"development_backfill"
    out_json=work/"report.json"
    out_csv=work/"coverage.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter),
        "--project-root",str(root),
        "--resolver-authority-json",str(resolve(root,args.resolver_authority_json)),
        "--backfill-authority-json",str(resolve(root,args.backfill_authority_json)),
        "--matrix-root",str(resolve(root,args.development_matrix_root)),
        "--replay-root",str(resolve(root,args.replay_root)),
        "--daily-materialization-root",str(resolve(root,args.daily_materialization_root)),
        "--output-root",str(out_root),
        "--output-json",str(out_json),
        "--output-csv",str(out_csv),
        "--partition-end",DEV_END,
        "--expected-matrix-symbol-count",str(DEV_SYMBOLS),
        "--expected-matrix-row-count",str(DEV_ROWS),
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_8_4_3_CARDINALITY_ADAPTER_DEVELOPMENT_EXECUTION_FAILED",
            "source_adapter_sha256":sha256_file(source),
            "candidate_adapter_sha256":sha256_file(adapter),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-12000:],
            "stderr_tail":proc.stderr[-12000:],
            "development_parity_certified":False,
            "validation_execution_authorized":False,
            "validation_outcomes_opened":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_4_1_DEVELOPMENT_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,args.output_json),report)
        shutil.rmtree(work,ignore_errors=True)
        print("=== M77.19.8.7.10.5.2.4.1 EXACT 8.4.3 INPUT CARDINALITY PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_8_4_3_CARDINALITY_ADAPTER_DEVELOPMENT_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("development_parity_certified: False")
        print("validation_execution_authorized: False")
        print("validation_outcomes_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,args.output_json))
        return 0

    expf,actf,erows,arows,missing,extra,mismatch=compare_dirs(
        resolve(root,args.certified_development_backfill_root),out_root
    )
    parity_ok=(
        expf==DEV_SYMBOLS and actf==DEV_SYMBOLS and
        erows==DEV_ROWS and arows==DEV_ROWS and
        not missing and not extra and not mismatch
    )
    status="READY" if parity_ok else "BLOCKED_8_4_3_CARDINALITY_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"

    report={
        "version":VERSION,
        "status":status,
        "source_adapter_sha256":sha256_file(source),
        "candidate_adapter_sha256":sha256_file(adapter),
        "parameterization_scope":"EXPECTED_INPUT_SYMBOL_AND_ROW_CARDINALITY_ONLY",
        "row_cardinality_assertions_parameterized_count":replacements,
        "development_expected_symbol_count":DEV_SYMBOLS,
        "development_expected_row_count":DEV_ROWS,
        "expected_symbol_file_count":expf,
        "actual_symbol_file_count":actf,
        "expected_row_count":erows,
        "actual_row_count":arows,
        "missing_symbol_files":missing,
        "extra_symbol_files":extra,
        "mismatch_symbol_count":len(mismatch),
        "development_parity_certified":parity_ok,
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_execution_authorized":parity_ok,
        "validation_outcomes_opened":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "RERUN_M77_19_8_7_10_5_2_4_WITH_CERTIFIED_CARDINALITY_PARAMETERIZED_8_4_3_ADAPTER"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_2_4_1_DEVELOPMENT_PARITY_MISMATCH"
        ),
    }

    if parity_ok:
        dst=root/"scripts/run_m77_19_8_4_3_cardinality_parameterized_certified.py"
        shutil.copy2(adapter,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)

    atomic_json(resolve(root,args.output_json),report)
    shutil.rmtree(work,ignore_errors=True)

    print("=== M77.19.8.7.10.5.2.4.1 EXACT 8.4.3 INPUT CARDINALITY PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("parameterization_scope: EXPECTED_INPUT_SYMBOL_AND_ROW_CARDINALITY_ONLY")
    print("row_cardinality_assertions_parameterized_count:",replacements)
    print("expected_symbol_file_count:",expf)
    print("actual_symbol_file_count:",actf)
    print("expected_row_count:",erows)
    print("actual_row_count:",arows)
    print("missing_symbol_file_count:",len(missing))
    print("extra_symbol_file_count:",len(extra))
    print("mismatch_symbol_count:",len(mismatch))
    print("development_parity_certified:",parity_ok)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_execution_authorized:",parity_ok)
    print("validation_outcomes_opened: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    if parity_ok:
        print("certified_adapter_script:",report["certified_adapter_script"])
        print("certified_adapter_script_sha256:",report["certified_adapter_script_sha256"])
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
