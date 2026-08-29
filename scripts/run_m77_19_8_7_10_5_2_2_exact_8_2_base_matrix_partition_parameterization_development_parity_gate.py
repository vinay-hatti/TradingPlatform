#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, gzip, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.2-EXACT-8.2-BASE-MATRIX-PARTITION-PARAMETERIZATION-DEVELOPMENT-PARITY-GATE-1.0"
DEV_END="2017-12-31"
EXPECTED_DEV_SYMBOLS=524
EXPECTED_DEV_ROWS=303689

class GateError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f: return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp")
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True); f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def iter_rows(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except Exception as exc: raise GateError(f"{path}:{i}: invalid JSONL") from exc

def row_hash(row):
    return hashlib.sha256(
        json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    ).hexdigest()

def compare_dirs(expected_root,actual_root):
    exp={p.name:p for p in Path(expected_root).glob("*.jsonl.gz")}
    act={p.name:p for p in Path(actual_root).glob("*.jsonl.gz")}
    missing=sorted(set(exp)-set(act))
    extra=sorted(set(act)-set(exp))
    mismatches=[]
    erows=0
    arows=0
    for name in sorted(set(exp)&set(act)):
        e=list(iter_rows(exp[name]))
        a=list(iter_rows(act[name]))
        erows += len(e)
        arows += len(a)
        if len(e)!=len(a) or any(row_hash(x)!=row_hash(y) for x,y in zip(e,a)):
            mismatches.append(name[:-9])
    return len(exp),len(act),erows,arows,missing,extra,mismatches

def discover_parse_assignment(text):
    tree=ast.parse(text)
    found=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.Assign,ast.AnnAssign)): continue
        value=node.value
        if not isinstance(value,ast.Call): continue
        fn=value.func
        if not (isinstance(fn,ast.Attribute) and fn.attr=="parse_args"): continue
        if isinstance(node,ast.Assign):
            if len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name): continue
            target=node.targets[0].id
        else:
            if not isinstance(node.target,ast.Name): continue
            target=node.target.id
        found.append((node.lineno,getattr(node,"end_lineno",node.lineno),target))
    if len(found)!=1:
        raise GateError(f"8.2 parse_args assignment discovery expected 1, found {len(found)}")
    return found[0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_5_2_1_validation_base_matrix_partition_coupling_forensics.json")
    ap.add_argument("--source-script",default="scripts/run_m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--certified-development-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_2_exact_8_2_base_matrix_partition_parameterization_development_parity_gate.json")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    forensic_path=resolve(root,a.forensics_json)
    forensic=load_json(forensic_path)
    source=resolve(root,a.source_script)

    if forensic.get("status")!="READY" or forensic.get("root_cause_certified") is not True:
        raise GateError("10.5.2.1 forensics not READY/certified")
    if forensic.get("root_cause")!="CERTIFIED_8_4_3_ADAPTER_RECEIVED_DEVELOPMENT_ONLY_8_2_BASE_MATRIX":
        raise GateError("unexpected 10.5.2.1 root cause")
    if sha256_file(source)!=forensic.get("development_base_matrix_script_sha256"):
        raise GateError("8.2 source SHA changed after forensics")
    if forensic.get("validation_outcomes_opened") is not False or forensic.get("final_holdout_opened") is not False:
        raise GateError("partition governance violated")

    original=source.read_text(encoding="utf-8")
    adapter=original

    # Preserve the module-level DEV_END literal exactly. Parameterize at runtime,
    # after the actual parse_args assignment, using AST-discovered target name.
    parser_anchor="argparse.ArgumentParser("
    if parser_anchor not in adapter:
        raise GateError("8.2 ArgumentParser construction not discoverable")

    # Insert --partition-end immediately after the first parser assignment's line.
    tree=ast.parse(adapter)
    parser_assign=None
    parser_name=None
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            v=node.value
            if isinstance(v,ast.Call):
                fn=v.func
                if isinstance(fn,ast.Attribute) and fn.attr=="ArgumentParser":
                    parser_assign=node
                    parser_name=node.targets[0].id
                    break
                if isinstance(fn,ast.Name) and fn.id=="ArgumentParser":
                    parser_assign=node
                    parser_name=node.targets[0].id
                    break
    if parser_assign is None or parser_name is None:
        # Common source form is ap=argparse.ArgumentParser()
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                v=node.value
                if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute):
                    if isinstance(v.func.value,ast.Name) and v.func.value.id=="argparse" and v.func.attr=="ArgumentParser":
                        parser_assign=node
                        parser_name=node.targets[0].id
                        break
    if parser_assign is None:
        raise GateError("8.2 parser assignment not discoverable")

    lines=adapter.splitlines()
    pend=getattr(parser_assign,"end_lineno",parser_assign.lineno)
    indent=lines[parser_assign.lineno-1][:len(lines[parser_assign.lineno-1])-len(lines[parser_assign.lineno-1].lstrip())]
    lines[pend:pend]=[
        indent+f'{parser_name}.add_argument("--partition-end",default="{DEV_END}")'
    ]
    adapter="\n".join(lines)+"\n"

    # Reparse because line numbers shifted, then discover parse_args structurally.
    start,end,args_name=discover_parse_assignment(adapter)
    lines=adapter.splitlines()
    indent=lines[start-1][:len(lines[start-1])-len(lines[start-1].lstrip())]
    injection=[
        indent+"# M77.19.8.7.10.5.2.2 runtime-only partition override",
        indent+f'globals()["DEV_END"]={args_name}.partition_end',
    ]
    lines[end:end]=injection
    adapter="\n".join(lines)+"\n"

    # Fail closed against illegal module-level mutation or feature-code rewriting.
    if "DEV_END=a.partition_end" in adapter or "DEV_END = a.partition_end" in adapter:
        raise GateError("adapter illegally rewrote module-level DEV_END")
    compile(adapter,"<m77_19_8_7_10_5_2_2_adapter>","exec")

    work=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_2_2_",dir=str(root/"research_data")))
    adapter_script=work/"run_m77_19_8_2_partition_parameterized.py"
    adapter_script.write_text(adapter,encoding="utf-8")
    out_root=work/"development_base_matrix"
    out_json=work/"development_base_matrix_report.json"
    out_csv=work/"development_base_matrix_schema.csv"

    py=str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python"
    cmd=[
        py,str(adapter_script),
        "--project-root",str(root),
        "--feature-authority-json",str(resolve(root,a.feature_authority_json)),
        "--replay-authority-json",str(resolve(root,a.replay_authority_json)),
        "--replay-root",str(resolve(root,a.replay_root)),
        "--context-csv",str(resolve(root,a.context_csv)),
        "--output-root",str(out_root),
        "--output-json",str(out_json),
        "--output-csv",str(out_csv),
        "--partition-end",DEV_END,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,
            "status":"BLOCKED_8_2_ADAPTER_DEVELOPMENT_EXECUTION_FAILED",
            "source_script_sha256":sha256_file(source),
            "adapter_script_sha256":sha256_file(adapter_script),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "adapter_development_parity_certified":False,
            "validation_base_matrix_execution_authorized":False,
            "validation_outcomes_opened":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_2_8_2_ADAPTER_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,a.output_json),report)
        shutil.rmtree(work,ignore_errors=True)
        print("=== M77.19.8.7.10.5.2.2 EXACT 8.2 BASE-MATRIX PARTITION PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_8_2_ADAPTER_DEVELOPMENT_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("adapter_development_parity_certified: False")
        print("validation_base_matrix_execution_authorized: False")
        print("validation_outcomes_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,a.output_json))
        return 0

    expf,actf,erows,arows,missing,extra,mismatch=compare_dirs(
        resolve(root,a.certified_development_root),out_root
    )
    parity_ok=(
        expf==EXPECTED_DEV_SYMBOLS and actf==EXPECTED_DEV_SYMBOLS and
        erows==EXPECTED_DEV_ROWS and arows==EXPECTED_DEV_ROWS and
        not missing and not extra and not mismatch
    )

    status="READY" if parity_ok else "BLOCKED_8_2_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"
    report={
        "version":VERSION,
        "status":status,
        "forensics_sha256":sha256_file(forensic_path),
        "source_script_sha256":sha256_file(source),
        "adapter_script_sha256":sha256_file(adapter_script),
        "partition_parameterization_scope":"PARTITION_END_RUNTIME_BINDING_ONLY",
        "development_partition_end_used":DEV_END,
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
        "semantic_equivalent_rewrite_performed":False,
        "validation_base_matrix_execution_authorized":parity_ok,
        "validation_base_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_3_EXACT_8_2_VALIDATION_BASE_MATRIX_MATERIALIZATION"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_2_2_8_2_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"
        )
    }

    if parity_ok:
        dst=root/"scripts/run_m77_19_8_2_partition_parameterized_certified.py"
        shutil.copy2(adapter_script,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)

    atomic_json(resolve(root,a.output_json),report)
    shutil.rmtree(work,ignore_errors=True)

    print("=== M77.19.8.7.10.5.2.2 EXACT 8.2 BASE-MATRIX PARTITION PARAMETERIZATION & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("partition_parameterization_scope: PARTITION_END_RUNTIME_BINDING_ONLY")
    print("expected_symbol_file_count:",expf)
    print("actual_symbol_file_count:",actf)
    print("expected_row_count:",erows)
    print("actual_row_count:",arows)
    print("missing_symbol_file_count:",len(missing))
    print("extra_symbol_file_count:",len(extra))
    print("mismatch_symbol_count:",len(mismatch))
    print("adapter_development_parity_certified:",parity_ok)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
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
    print("report:",resolve(root,a.output_json))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
