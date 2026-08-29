#!/usr/bin/env python3
from __future__ import annotations

import argparse,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.3.4-EXACT-8.2-PARTITION-ROUTING-PARAMETERIZATION-DEVELOPMENT-PARITY-GATE-1.0"
DEV_START=""
DEV_END="2017-12-31"
DEV_PARTITION="DEVELOPMENT"
EXPECTED_DEV_SYMBOLS=524
EXPECTED_DEV_ROWS=303689

class GateError(RuntimeError): pass

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
            except Exception as exc:raise GateError(f"{path}:{i}: invalid JSONL") from exc

def row_hash(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

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
    ap.add_argument("--failed-validation-json",default="reports/m77_19_8_7_10_5_2_3_3_exact_8_2_validation_partition_base_matrix_materialization.json")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_5_2_3_1_exact_8_2_partition_gate_forensics.json")
    ap.add_argument("--source-script",default="scripts/run_m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--certified-development-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_3_4_exact_8_2_partition_routing_parameterization_development_parity_gate.json")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    failed=load_json(resolve(root,args.failed_validation_json))
    forensic=load_json(resolve(root,args.forensics_json))
    source=resolve(root,args.source_script)

    if failed.get("status")!="BLOCKED_VALIDATION_PARTITION_BASE_MATRIX_CERTIFICATION_FAILURE":
        raise GateError("10.5.2.3.3 not in expected blocked state")
    if failed.get("validation_row_count")!=EXPECTED_DEV_ROWS or failed.get("partition_mismatch_row_count")!=EXPECTED_DEV_ROWS:
        raise GateError("10.5.2.3.3 failure mode changed")
    if forensic.get("status")!="READY":
        raise GateError("10.5.2.3.1 forensics not READY")
    if sha256_file(source)!=forensic.get("source_script_sha256"):
        raise GateError("8.2 source SHA changed after forensics")
    if failed.get("validation_outcomes_opened") is not False or failed.get("final_holdout_opened") is not False:
        raise GateError("partition governance violated")

    adapter=source.read_text(encoding="utf-8")

    dev_anchor='DEV_END="2017-12-31"'
    if dev_anchor not in adapter:
        raise GateError("canonical DEV_END declaration not found")
    adapter=adapter.replace(
        dev_anchor,
        dev_anchor+'\nACTIVE_PARTITION_START=""\nACTIVE_PARTITION_END=DEV_END\nACTIVE_PARTITION_LABEL="DEVELOPMENT"',
        1
    )

    parser_anchor='ap=argparse.ArgumentParser()'
    if parser_anchor not in adapter:
        raise GateError("canonical argparse parser anchor not found")
    adapter=adapter.replace(
        parser_anchor,
        parser_anchor+
        '\n    ap.add_argument("--partition-start",default="")'+
        '\n    ap.add_argument("--partition-end",default="2017-12-31")'+
        '\n    ap.add_argument("--partition-label",default="DEVELOPMENT")',
        1
    )

    parse_anchor='args=ap.parse_args()'
    if parse_anchor not in adapter:
        raise GateError("canonical parse_args anchor not found")
    adapter=adapter.replace(
        parse_anchor,
        parse_anchor+
        '\n    globals()["ACTIVE_PARTITION_START"]=args.partition_start'+
        '\n    globals()["ACTIVE_PARTITION_END"]=args.partition_end'+
        '\n    globals()["ACTIVE_PARTITION_LABEL"]=args.partition_label',
        1
    )

    old_context = (
        '            if as_of<=DEV_END and r.get("partition")=="DEVELOPMENT":\n'
        '                context[as_of]=r\n'
        '            elif VALIDATION_START<=as_of<FINAL_HOLDOUT_START:\n'
        '                validation_context_rows_seen_and_skipped+=1\n'
        '            elif as_of>=FINAL_HOLDOUT_START:\n'
        '                final_holdout_context_rows_seen+=1'
    )
    new_context = (
        '            if as_of>=FINAL_HOLDOUT_START:\n'
        '                final_holdout_context_rows_seen+=1\n'
        '            elif ACTIVE_PARTITION_LABEL=="DEVELOPMENT":\n'
        '                if as_of<=ACTIVE_PARTITION_END and r.get("partition")==ACTIVE_PARTITION_LABEL:\n'
        '                    context[as_of]=r\n'
        '                elif VALIDATION_START<=as_of<FINAL_HOLDOUT_START:\n'
        '                    validation_context_rows_seen_and_skipped+=1\n'
        '            elif ACTIVE_PARTITION_LABEL=="VALIDATION":\n'
        '                if ACTIVE_PARTITION_START<=as_of<=ACTIVE_PARTITION_END and r.get("partition")==ACTIVE_PARTITION_LABEL:\n'
        '                    context[as_of]=r\n'
        '            else:\n'
        '                raise MatrixError(f"unsupported active partition label: {ACTIVE_PARTITION_LABEL}")'
    )
    if old_context not in adapter:
        raise GateError("canonical context routing block not found")
    adapter=adapter.replace(old_context,new_context,1)

    old_replay = (
        '            if as_of>=FINAL_HOLDOUT_START:\n'
        '                final_holdout_replay_rows_seen_and_skipped+=1\n'
        '                continue\n'
        '            if VALIDATION_START<=as_of<FINAL_HOLDOUT_START:\n'
        '                validation_replay_rows_seen_and_skipped+=1\n'
        '                continue\n'
        '            if not as_of or as_of>DEV_END:\n'
        '                continue'
    )
    new_replay = (
        '            if as_of>=FINAL_HOLDOUT_START:\n'
        '                final_holdout_replay_rows_seen_and_skipped+=1\n'
        '                continue\n'
        '            if ACTIVE_PARTITION_LABEL=="DEVELOPMENT":\n'
        '                if VALIDATION_START<=as_of<FINAL_HOLDOUT_START:\n'
        '                    validation_replay_rows_seen_and_skipped+=1\n'
        '                    continue\n'
        '                if not as_of or as_of>ACTIVE_PARTITION_END:\n'
        '                    continue\n'
        '            elif ACTIVE_PARTITION_LABEL=="VALIDATION":\n'
        '                if not as_of or as_of<ACTIVE_PARTITION_START or as_of>ACTIVE_PARTITION_END:\n'
        '                    continue\n'
        '            else:\n'
        '                raise MatrixError(f"unsupported active partition label: {ACTIVE_PARTITION_LABEL}")'
    )
    if old_replay not in adapter:
        raise GateError("canonical replay routing block not found")
    adapter=adapter.replace(old_replay,new_replay,1)

    adapter=adapter.replace(
        '"development_end":DEV_END,',
        '"development_end":DEV_END,\n'
        '        "active_partition_start":ACTIVE_PARTITION_START,\n'
        '        "active_partition_end":ACTIVE_PARTITION_END,\n'
        '        "active_partition_label":ACTIVE_PARTITION_LABEL,',
        1
    )
    adapter=adapter.replace(
        '"development_only":True,',
        '"development_only":ACTIVE_PARTITION_LABEL=="DEVELOPMENT",',
        1
    )

    if adapter.count('as_of>=FINAL_HOLDOUT_START') < 2:
        raise GateError("Final Holdout context/replay gates not both preserved")
    if 'ACTIVE_PARTITION_LABEL=="VALIDATION"' not in adapter:
        raise GateError("Validation routing branch missing")

    compile(adapter,"<m77_19_8_7_10_5_2_3_4_adapter>","exec")

    work=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_2_3_4_",dir=str(root/"research_data")))
    adapter_script=work/"run_m77_19_8_2_partition_routing_parameterized.py"
    adapter_script.write_text(adapter,encoding="utf-8")
    out_root=work/"development_matrix"
    out_json=work/"report.json"
    out_csv=work/"schema.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter_script),
        "--project-root",str(root),
        "--feature-authority-json",str(resolve(root,args.feature_authority_json)),
        "--replay-authority-json",str(resolve(root,args.replay_authority_json)),
        "--replay-root",str(resolve(root,args.replay_root)),
        "--context-csv",str(resolve(root,args.context_csv)),
        "--output-root",str(out_root),
        "--output-json",str(out_json),
        "--output-csv",str(out_csv),
        "--partition-start",DEV_START,
        "--partition-end",DEV_END,
        "--partition-label",DEV_PARTITION,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_8_2_PARTITION_ROUTING_ADAPTER_EXECUTION_FAILED",
            "source_script_sha256":sha256_file(source),
            "adapter_script_sha256":sha256_file(adapter_script),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "adapter_development_parity_certified":False,
            "validation_base_matrix_execution_authorized":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_3_4_ADAPTER_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,args.output_json),report)
        shutil.rmtree(work,ignore_errors=True)
        print("=== M77.19.8.7.10.5.2.3.4 EXACT 8.2 PARTITION ROUTING PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_8_2_PARTITION_ROUTING_ADAPTER_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("adapter_development_parity_certified: False")
        print("validation_base_matrix_execution_authorized: False")
        print("validation_targets_opened: False")
        print("validation_outcomes_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,args.output_json))
        return 0

    expf,actf,erows,arows,missing,extra,mismatch=compare_dirs(
        resolve(root,args.certified_development_root),out_root
    )
    parity_ok=(
        expf==EXPECTED_DEV_SYMBOLS and actf==EXPECTED_DEV_SYMBOLS and
        erows==EXPECTED_DEV_ROWS and arows==EXPECTED_DEV_ROWS and
        not missing and not extra and not mismatch
    )
    status="READY" if parity_ok else "BLOCKED_8_2_PARTITION_ROUTING_DEVELOPMENT_PARITY_MISMATCH"

    report={
        "version":VERSION,
        "status":status,
        "failed_validation_sha256":sha256_file(resolve(root,args.failed_validation_json)),
        "forensics_sha256":sha256_file(resolve(root,args.forensics_json)),
        "source_script_sha256":sha256_file(source),
        "adapter_script_sha256":sha256_file(adapter_script),
        "parameterization_scope":"PARTITION_ROUTING_START_END_LABEL_ONLY",
        "development_partition_start_used":DEV_START,
        "development_partition_end_used":DEV_END,
        "development_partition_label_used":DEV_PARTITION,
        "final_holdout_skip_unconditional":True,
        "expected_symbol_file_count":expf,
        "actual_symbol_file_count":actf,
        "expected_row_count":erows,
        "actual_row_count":arows,
        "missing_symbol_files":missing,
        "extra_symbol_files":extra,
        "mismatch_symbol_count":len(mismatch),
        "mismatch_symbols":mismatch,
        "adapter_development_parity_certified":parity_ok,
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_feature_rewrite_performed":False,
        "validation_base_matrix_execution_authorized":parity_ok,
        "validation_base_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_3_5_EXACT_8_2_VALIDATION_ROUTED_BASE_MATRIX_MATERIALIZATION"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_2_3_4_DEVELOPMENT_PARITY_MISMATCH"
        ),
    }

    if parity_ok:
        dst=root/"scripts/run_m77_19_8_2_partition_routing_parameterized_certified.py"
        shutil.copy2(adapter_script,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)

    atomic_json(resolve(root,args.output_json),report)
    shutil.rmtree(work,ignore_errors=True)

    print("=== M77.19.8.7.10.5.2.3.4 EXACT 8.2 PARTITION ROUTING PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("parameterization_scope: PARTITION_ROUTING_START_END_LABEL_ONLY")
    print("final_holdout_skip_unconditional: True")
    print("expected_symbol_file_count:",expf)
    print("actual_symbol_file_count:",actf)
    print("expected_row_count:",erows)
    print("actual_row_count:",arows)
    print("missing_symbol_file_count:",len(missing))
    print("extra_symbol_file_count:",len(extra))
    print("mismatch_symbol_count:",len(mismatch))
    print("adapter_development_parity_certified:",parity_ok)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_feature_rewrite_performed: False")
    print("validation_base_matrix_execution_authorized:",parity_ok)
    print("validation_base_matrix_materialized: False")
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
