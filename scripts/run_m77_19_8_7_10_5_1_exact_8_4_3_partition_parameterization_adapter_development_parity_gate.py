#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.1-EXACT-8.4.3-PARTITION-PARAMETERIZATION-ADAPTER-DEVELOPMENT-PARITY-GATE-1.0"
EXPECTED_DEV_ROWS=303689
EXPECTED_DEV_FILES=524

class AdapterError(RuntimeError):pass

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
            except Exception as exc:raise AdapterError(f"{path}:{i}: invalid JSONL") from exc
def row_hash(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def compare_dirs(expected_root,actual_root):
    exp={p.name:p for p in expected_root.glob("*.jsonl.gz")}
    act={p.name:p for p in actual_root.glob("*.jsonl.gz")}
    missing=sorted(set(exp)-set(act));extra=sorted(set(act)-set(exp))
    mismatch=[];erows=0;arows=0
    for name in sorted(set(exp)&set(act)):
        e=list(iter_rows(exp[name]));a=list(iter_rows(act[name]))
        erows+=len(e);arows+=len(a)
        if len(e)!=len(a) or any(row_hash(x)!=row_hash(y) for x,y in zip(e,a)):
            mismatch.append(name[:-9])
    return exp,act,missing,extra,mismatch,erows,arows

# M77.19.8.7.10.5.1.0.1-ADAPTER-GENERATION-ORDER-REPAIR
# M77.19.8.7.10.5.1.0.2-RUNTIME-PARTITION-CONSTANT-BINDING-REPAIR
# M77.19.8.7.10.5.1.0.3-AST-PARSE-ARGS-RUNTIME-BINDING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--blocked-validation-json",default="reports/m77_19_8_7_10_5_exact_main_reuse_validation_feature_matrix_materialization.json")
    ap.add_argument("--development-parity-json",default="reports/m77_19_8_7_10_4_2_exact_main_development_replay_parity_harness.json")
    ap.add_argument("--source-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--certified-development-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_1_exact_8_4_3_partition_parameterization_adapter_development_parity_gate.json")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    blocked=load_json(resolve(root,a.blocked_validation_json))
    parity=load_json(resolve(root,a.development_parity_json))
    src=resolve(root,a.source_script)

    if blocked.get("status")!="BLOCKED_EXACT_8_4_3_PARTITION_PARAMETERIZATION_ADAPTER_REQUIRED":
        raise AdapterError("10.5 not in expected blocked state")
    if blocked.get("validation_outcomes_opened") is not False or blocked.get("final_holdout_opened") is not False:
        raise AdapterError("partition governance violated")
    if parity.get("status")!="READY" or parity.get("development_parity_certified") is not True:
        raise AdapterError("10.4.2 parity not certified")
    if sha256_file(src)!=parity.get("development_backfill_script_sha256"):
        raise AdapterError("8.4.3 source SHA changed")

    text=src.read_text(encoding="utf-8")
    tree=ast.parse(text)
    constants=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and isinstance(node.value,str):
            if node.value in ("2017-12-31","DEVELOPMENT","DEVELOPMENT_ONLY"):
                constants.append({"value":node.value,"lineno":getattr(node,"lineno",None)})
    if not constants:
        raise AdapterError("Development partition constants not discoverable")

    # Build an adapter copy mechanically, changing only the partition end date
    # from 2017-12-31 to a CLI-supplied value. The default remains 2017-12-31,
    # preserving exact Development behavior.
    adapter_dir=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_1_",dir=str(root/"research_data")))
    adapter_script=adapter_dir/"run_m77_19_8_4_3_partition_parameterized.py"
    adapted=text

    # M77.19.8.7.10.5.1.0.2:
    # Keep all frozen module-level Development constants exactly as authored.
    # Parameterize only at runtime after argparse has produced `a`.
    parser_anchor="ap=argparse.ArgumentParser()"
    if parser_anchor not in adapted:
        raise AdapterError("8.4.3 argparse anchor missing")

    adapted=adapted.replace(
        parser_anchor,
        parser_anchor + '\n    ap.add_argument("--partition-end",default="2017-12-31")',
        1
    )

    # M77.19.8.7.10.5.1.0.3:
    # Discover the actual parse_args assignment structurally instead of assuming
    # exact formatting such as `a=ap.parse_args()`.
    adapter_tree=ast.parse(adapted)
    parse_assignments=[]
    for node in ast.walk(adapter_tree):
        if not isinstance(node,(ast.Assign,ast.AnnAssign)):
            continue
        value=node.value if isinstance(node,ast.AnnAssign) else node.value
        if not isinstance(value,ast.Call):
            continue
        fn=value.func
        if not (isinstance(fn,ast.Attribute) and fn.attr=="parse_args"):
            continue
        if isinstance(node,ast.Assign):
            if len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):
                continue
            target_name=node.targets[0].id
        else:
            if not isinstance(node.target,ast.Name):
                continue
            target_name=node.target.id
        parse_assignments.append((node.lineno,getattr(node,"end_lineno",node.lineno),target_name))

    if len(parse_assignments)!=1:
        raise AdapterError(
            f"8.4.3 parse_args assignment discovery expected 1, found {len(parse_assignments)}"
        )

    start_line,end_line,args_name=parse_assignments[0]
    adapter_lines=adapted.splitlines()
    indent=adapter_lines[start_line-1][:len(adapter_lines[start_line-1])-len(adapter_lines[start_line-1].lstrip())]
    injection=(
        indent+"# M77.19.8.7.10.5.1.0.3 runtime-only partition override"
        + "\n"
        + indent+f'globals()["DEV_END"]={args_name}.partition_end'
    )
    adapter_lines[end_line:end_line]=injection.splitlines()
    adapted="\n".join(adapter_lines)+"\n"

    # Fail closed if any module-level assignment was rewritten to depend on args.
    for bad in (
        "DEV_END=a.partition_end",
        'DEV_END = a.partition_end',
        "DEV_END =a.partition_end",
        'DEV_END= a.partition_end',
    ):
        if bad in adapted:
            raise AdapterError("adapter generation illegally parameterized module-level DEV_END")
    adapter_script.write_text(adapted,encoding="utf-8")

    # Syntax certification.
    try:
        compile(adapted,str(adapter_script),"exec")
    except Exception as exc:
        raise AdapterError(f"adapter syntax invalid: {exc}")

    tmp_out=adapter_dir/"dev_out"
    tmp_json=adapter_dir/"dev_report.json"
    tmp_csv=adapter_dir/"dev_cov.csv"
    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter_script),
        "--project-root",str(root),
        "--resolver-authority-json",str(resolve(root,a.resolver_authority_json)),
        "--backfill-authority-json",str(resolve(root,a.backfill_authority_json)),
        "--matrix-root",str(resolve(root,a.matrix_root)),
        "--replay-root",str(resolve(root,a.replay_root)),
        "--daily-materialization-root",str(resolve(root,a.daily_materialization_root)),
        "--output-root",str(tmp_out),
        "--output-json",str(tmp_json),
        "--output-csv",str(tmp_csv),
        "--partition-end","2017-12-31",
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,"status":"BLOCKED_ADAPTER_DEVELOPMENT_EXECUTION_FAILED",
            "source_script_sha256":sha256_file(src),
            "adapter_script_sha256":sha256_file(adapter_script),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "adapter_development_parity_certified":False,
            "validation_execution_authorized":False,
            "validation_outcomes_opened":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_1_ADAPTER_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,a.output_json),report)
        shutil.rmtree(adapter_dir,ignore_errors=True)
        print("=== M77.19.8.7.10.5.1 EXACT 8.4.3 PARTITION-PARAMETERIZATION ADAPTER & DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_ADAPTER_DEVELOPMENT_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("adapter_development_parity_certified: False")
        print("validation_execution_authorized: False")
        print("validation_outcomes_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,a.output_json))
        return 0

    exp,act,missing,extra,mismatch,erows,arows=compare_dirs(
        resolve(root,a.certified_development_root),tmp_out
    )
    parity_ok=(
        len(exp)==EXPECTED_DEV_FILES and len(act)==EXPECTED_DEV_FILES and
        erows==EXPECTED_DEV_ROWS and arows==EXPECTED_DEV_ROWS and
        not missing and not extra and not mismatch
    )

    status="READY" if parity_ok else "BLOCKED_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"
    report={
        "version":VERSION,"status":status,
        "source_script_sha256":sha256_file(src),
        "adapter_script_sha256":sha256_file(adapter_script),
        "partition_parameterization_scope":"PARTITION_END_ONLY",
        "default_partition_end":"2017-12-31",
        "development_partition_end_used":"2017-12-31",
        "expected_symbol_file_count":len(exp),
        "actual_symbol_file_count":len(act),
        "expected_row_count":erows,
        "actual_row_count":arows,
        "missing_symbol_files":missing,
        "extra_symbol_files":extra,
        "mismatch_symbol_count":len(mismatch),
        "mismatch_symbols":mismatch,
        "adapter_development_parity_certified":parity_ok,
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_execution_authorized":parity_ok,
        "validation_feature_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_EXACT_ADAPTER_VALIDATION_FEATURE_MATRIX_MATERIALIZATION"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_1_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"
        ),
    }
    atomic_json(resolve(root,a.output_json),report)

    # Persist only the adapter source after successful parity so 10.5.2 can use
    # the exact certified artifact. Otherwise discard it.
    if parity_ok:
        dst=root/"scripts/run_m77_19_8_4_3_partition_parameterized_certified.py"
        shutil.copy2(adapter_script,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)
        atomic_json(resolve(root,a.output_json),report)

    shutil.rmtree(adapter_dir,ignore_errors=True)

    print("=== M77.19.8.7.10.5.1 EXACT 8.4.3 PARTITION-PARAMETERIZATION ADAPTER & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("partition_parameterization_scope: PARTITION_END_ONLY")
    print("expected_symbol_file_count:",len(exp))
    print("actual_symbol_file_count:",len(act))
    print("expected_row_count:",erows)
    print("actual_row_count:",arows)
    print("missing_symbol_file_count:",len(missing))
    print("extra_symbol_file_count:",len(extra))
    print("mismatch_symbol_count:",len(mismatch))
    print("adapter_development_parity_certified:",parity_ok)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_execution_authorized:",parity_ok)
    print("validation_feature_matrix_materialized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    if parity_ok:
        print("certified_adapter_script: scripts/run_m77_19_8_4_3_partition_parameterized_certified.py")
        print("certified_adapter_script_sha256:",report["certified_adapter_script_sha256"])
    print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json))
    return 0

if __name__=="__main__":raise SystemExit(main())
