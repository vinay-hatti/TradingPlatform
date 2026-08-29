#!/usr/bin/env python3
from __future__ import annotations

import argparse,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.4.4-EXACT-8.4.3-PARTITION-ROW-ADMISSION-PARAMETERIZATION-DEVELOPMENT-PARITY-GATE-1.0"
DEV_START=""
DEV_END="2017-12-31"
DEV_PARTITION="DEVELOPMENT"
DEV_SYMBOLS=524
DEV_ROWS=303689

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

def replace_once(text,old,new,label):
    if old not in text:
        raise GateError(f"{label} anchor missing")
    return text.replace(old,new,1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_5_2_4_3_exact_8_4_3_validation_row_admission_forensics.json")
    ap.add_argument("--source-adapter-script",default="scripts/run_m77_19_8_4_3_cardinality_parameterized_certified.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--development-matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--certified-development-backfill-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_4_4_exact_8_4_3_partition_row_admission_parameterization_development_parity_gate.json")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    fx=load_json(resolve(root,args.forensics_json))
    source=resolve(root,args.source_adapter_script)

    if fx.get("status")!="READY" or fx.get("failure_signature")!="DEVELOPMENT_ROW_COUNT_CHANGED_ZERO":
        raise GateError("10.5.2.4.3 forensics not READY/expected")
    if sha256_file(source)!=fx.get("certified_adapter_script_sha256"):
        raise GateError("certified adapter SHA changed after forensics")
    if fx.get("validation_outcomes_opened") is not False or fx.get("final_holdout_opened") is not False:
        raise GateError("governance violation")

    text=source.read_text(encoding="utf-8")

    parser_anchor='ap=argparse.ArgumentParser()'
    text=replace_once(
        text,
        parser_anchor,
        parser_anchor+
        '\n    ap.add_argument("--active-partition-start",default="")'+
        '\n    ap.add_argument("--active-partition-end",default="2017-12-31")'+
        '\n    ap.add_argument("--active-partition-label",default="DEVELOPMENT")',
        "argparse"
    )

    old_replay='if d<=DEV_END and r.get("status")=="REPLAYED"'
    new_replay='if (not args.active_partition_start or d>=args.active_partition_start) and d<=args.active_partition_end and r.get("status")=="REPLAYED"'
    text=replace_once(text,old_replay,new_replay,"replay provenance date gate")

    if 'if d>=VALIDATION_START:' in text:
        text=text.replace(
            'if d>=VALIDATION_START:',
            'if args.active_partition_label=="DEVELOPMENT" and d>=VALIDATION_START:',
            1
        )
    elif 'if d >= VALIDATION_START:' in text:
        text=text.replace(
            'if d >= VALIDATION_START:',
            'if args.active_partition_label=="DEVELOPMENT" and d>=VALIDATION_START:',
            1
        )
    else:
        raise GateError("Validation skip gate not found")

    anchor='            if rrw is None:raise RepairError(f"{symbol} {d}: replay provenance missing")'
    gate=(
        '            if args.active_partition_label=="VALIDATION":\n'
        '                if d<args.active_partition_start or d>args.active_partition_end:\n'
        '                    continue\n'
        '            elif args.active_partition_label=="DEVELOPMENT":\n'
        '                if args.active_partition_start and d<args.active_partition_start:\n'
        '                    continue\n'
        '                if d>args.active_partition_end:\n'
        '                    continue\n'
        '            else:\n'
        '                raise RepairError(f"unsupported active partition label: {args.active_partition_label}")\n'
        '            if rrw is None:raise RepairError(f"{symbol} {d}: replay provenance missing")'
    )
    text=replace_once(text,anchor,gate,"pre-provenance active-window admission")

    old_symbol=(
        '    if len(symbols)!=524:\n'
        '        raise RepairError(f"Development symbol count changed: {len(symbols)}")'
    )
    if old_symbol in text:
        text=text.replace(
            old_symbol,
            '    if len(symbols)!=args.expected_matrix_symbol_count:\n'
            '        raise RepairError(f"active partition symbol count changed: {len(symbols)}")',
            1
        )
    elif 'if len(symbols)!=524:' in text:
        text=text.replace('if len(symbols)!=524:','if len(symbols)!=args.expected_matrix_symbol_count:',1)
        text=text.replace('Development symbol count changed','active partition symbol count changed',1)
    else:
        raise GateError("Development symbol postcondition missing")

    old_nondev=(
        '    if validation_rows_materialized or final_holdout_rows_materialized:\n'
        '        raise RepairError("non-Development rows materialized")'
    )
    new_nondev=(
        '    if args.active_partition_label=="DEVELOPMENT":\n'
        '        if validation_rows_materialized or final_holdout_rows_materialized:\n'
        '            raise RepairError("non-Development rows materialized")\n'
        '    elif args.active_partition_label=="VALIDATION":\n'
        '        if final_holdout_rows_materialized:\n'
        '            raise RepairError("Final Holdout rows materialized during Validation")'
    )
    text=replace_once(text,old_nondev,new_nondev,"non-Development postcondition")

    if "final_holdout" not in text.lower():
        raise GateError("Final Holdout guard signals missing")

    compile(text,"<m77_19_8_7_10_5_2_4_4_adapter>","exec")

    work=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_2_4_4_",dir=str(root/"research_data")))
    adapter=work/"run_m77_19_8_4_3_partition_row_admission_parameterized.py"
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
        "--active-partition-start",DEV_START,
        "--active-partition-end",DEV_END,
        "--active-partition-label",DEV_PARTITION,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_8_4_3_ROW_ADMISSION_ADAPTER_DEVELOPMENT_EXECUTION_FAILED",
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
            "next_step":"REVIEW_M77_19_8_7_10_5_2_4_4_DEVELOPMENT_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,args.output_json),report)
        shutil.rmtree(work,ignore_errors=True)
        print("=== M77.19.8.7.10.5.2.4.4 EXACT 8.4.3 PARTITION ROW-ADMISSION PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_8_4_3_ROW_ADMISSION_ADAPTER_DEVELOPMENT_EXECUTION_FAILED")
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
    status="READY" if parity_ok else "BLOCKED_8_4_3_ROW_ADMISSION_DEVELOPMENT_PARITY_MISMATCH"

    report={
        "version":VERSION,
        "status":status,
        "forensics_sha256":sha256_file(resolve(root,args.forensics_json)),
        "source_adapter_sha256":sha256_file(source),
        "candidate_adapter_sha256":sha256_file(adapter),
        "parameterization_scope":"ACTIVE_PARTITION_START_END_LABEL_PLUS_EXISTING_INPUT_CARDINALITY",
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
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_4_5_CERTIFIED_8_4_3_VALIDATION_ROW_ADMISSION_INVOCATION"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_2_4_4_DEVELOPMENT_PARITY_MISMATCH"
        ),
    }

    if parity_ok:
        dst=root/"scripts/run_m77_19_8_4_3_partition_row_admission_parameterized_certified.py"
        shutil.copy2(adapter,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)

    atomic_json(resolve(root,args.output_json),report)
    shutil.rmtree(work,ignore_errors=True)

    print("=== M77.19.8.7.10.5.2.4.4 EXACT 8.4.3 PARTITION ROW-ADMISSION PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("parameterization_scope: ACTIVE_PARTITION_START_END_LABEL_PLUS_EXISTING_INPUT_CARDINALITY")
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
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
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
