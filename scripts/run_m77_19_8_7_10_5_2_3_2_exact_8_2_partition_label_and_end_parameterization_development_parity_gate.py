#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.3.2-EXACT-8.2-PARTITION-LABEL-AND-END-PARAMETERIZATION-DEVELOPMENT-PARITY-GATE-1.0"
DEV_END="2017-12-31"
DEV_PARTITION="DEVELOPMENT"
EXPECTED_DEV_SYMBOLS=524
EXPECTED_DEV_ROWS=303689

class GateError(RuntimeError):pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
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
            except Exception as exc:raise GateError(f"{path}:{i}: invalid JSONL") from exc
def row_hash(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def compare_dirs(expected_root,actual_root):
    exp={p.name:p for p in Path(expected_root).glob("*.jsonl.gz")}
    act={p.name:p for p in Path(actual_root).glob("*.jsonl.gz")}
    missing=sorted(set(exp)-set(act));extra=sorted(set(act)-set(exp))
    mismatch=[];erows=0;arows=0
    for name in sorted(set(exp)&set(act)):
        e=list(iter_rows(exp[name]));a=list(iter_rows(act[name]))
        erows+=len(e);arows+=len(a)
        if len(e)!=len(a) or any(row_hash(x)!=row_hash(y) for x,y in zip(e,a)):
            mismatch.append(name[:-9])
    return len(exp),len(act),erows,arows,missing,extra,mismatch

def discover_single_parse_args(text):
    tree=ast.parse(text);found=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.Assign,ast.AnnAssign)):continue
        value=node.value
        if not isinstance(value,ast.Call):continue
        fn=value.func
        if not (isinstance(fn,ast.Attribute) and fn.attr=="parse_args"):continue
        if isinstance(node,ast.Assign):
            if len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):continue
            target=node.targets[0].id
        else:
            if not isinstance(node.target,ast.Name):continue
            target=node.target.id
        found.append((node.lineno,getattr(node,"end_lineno",node.lineno),target))
    if len(found)!=1:raise GateError(f"parse_args discovery expected 1, found {len(found)}")
    return found[0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_5_2_3_1_exact_8_2_partition_gate_forensics.json")
    ap.add_argument("--source-script",default="scripts/run_m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.py")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--certified-development-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_3_2_exact_8_2_partition_label_and_end_parameterization_development_parity_gate.json")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    forensic_path=resolve(root,a.forensics_json)
    forensic=load_json(forensic_path)
    source=resolve(root,a.source_script)

    if forensic.get("status")!="READY":
        raise GateError("10.5.2.3.1 forensics not READY")
    if forensic.get("failed_validation_only_row_count")!=0:
        raise GateError("forensic failure mode changed")
    ranked=forensic.get("ranked_likely_partition_gates") or []
    if not ranked:
        raise GateError("no ranked partition gates")
    gate1=(ranked[0].get("test_source") or "").replace(" ","")
    expected='as_of<=DEV_ENDandr.get("partition")=="DEVELOPMENT"'.replace(" ","")
    if gate1!=expected:
        raise GateError(f"operative gate changed: {ranked[0].get('test_source')}")
    if sha256_file(source)!=forensic.get("source_script_sha256"):
        raise GateError("8.2 source SHA changed after forensics")
    if forensic.get("validation_outcomes_opened") is not False or forensic.get("final_holdout_opened") is not False:
        raise GateError("governance violated")

    original=source.read_text(encoding="utf-8")
    adapter=original

    # Add two runtime parameters, but preserve original module-level defaults.
    tree=ast.parse(adapter)
    parser_assign=None;parser_name=None
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            v=node.value
            if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute):
                if isinstance(v.func.value,ast.Name) and v.func.value.id=="argparse" and v.func.attr=="ArgumentParser":
                    parser_assign=node;parser_name=node.targets[0].id;break
    if parser_assign is None:raise GateError("8.2 parser assignment not discoverable")

    lines=adapter.splitlines()
    end=getattr(parser_assign,"end_lineno",parser_assign.lineno)
    indent=lines[parser_assign.lineno-1][:len(lines[parser_assign.lineno-1])-len(lines[parser_assign.lineno-1].lstrip())]
    lines[end:end]=[
        indent+f'{parser_name}.add_argument("--partition-end",default="{DEV_END}")',
        indent+f'{parser_name}.add_argument("--partition-label",default="{DEV_PARTITION}")',
    ]
    adapter="\n".join(lines)+"\n"

    start,end,args_name=discover_single_parse_args(adapter)
    lines=adapter.splitlines()
    indent=lines[start-1][:len(lines[start-1])-len(lines[start-1].lstrip())]
    lines[end:end]=[
        indent+"# M77.19.8.7.10.5.2.3.2 runtime-only partition controls",
        indent+f'globals()["DEV_END"]={args_name}.partition_end',
        indent+f'globals()["ACTIVE_PARTITION_LABEL"]={args_name}.partition_label',
    ]
    adapter="\n".join(lines)+"\n"

    # Replace only the exact certified partition predicate literal with ACTIVE_PARTITION_LABEL.
    old_gate='r.get("partition")=="DEVELOPMENT"'
    new_gate='r.get("partition")==ACTIVE_PARTITION_LABEL'
    if old_gate not in adapter:
        old_gate="r.get('partition')=='DEVELOPMENT'"
        new_gate="r.get('partition')==ACTIVE_PARTITION_LABEL"
    if old_gate not in adapter:
        raise GateError("certified DEVELOPMENT partition predicate not found")
    adapter=adapter.replace(old_gate,new_gate,1)

    # Insert module-level default for the active partition label next to DEV_END.
    dev_anchor='DEV_END="2017-12-31"'
    if dev_anchor not in adapter:
        dev_anchor="DEV_END='2017-12-31'"
    if dev_anchor not in adapter:
        raise GateError("module-level DEV_END literal missing")
    adapter=adapter.replace(dev_anchor,dev_anchor+'\nACTIVE_PARTITION_LABEL="DEVELOPMENT"',1)

    # Preserve Validation and Final Holdout safety gates verbatim.
    for protected in (
        "VALIDATION_START<=as_of<FINAL_HOLDOUT_START",
        "as_of>=FINAL_HOLDOUT_START",
    ):
        if protected not in adapter.replace(" ",""):
            raise GateError(f"protected partition safety gate missing: {protected}")

    compile(adapter,"<m77_19_8_7_10_5_2_3_2_adapter>","exec")

    work=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_5_2_3_2_",dir=str(root/"research_data")))
    adapter_script=work/"run_m77_19_8_2_partition_label_end_parameterized.py"
    adapter_script.write_text(adapter,encoding="utf-8")
    out_root=work/"development_matrix"
    out_json=work/"report.json"
    out_csv=work/"schema.csv"

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
        "--partition-label",DEV_PARTITION,
    ]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)

    if proc.returncode!=0:
        report={
            "version":VERSION,"status":"BLOCKED_8_2_PARTITION_LABEL_ADAPTER_EXECUTION_FAILED",
            "source_script_sha256":sha256_file(source),
            "adapter_script_sha256":sha256_file(adapter_script),
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],"stderr_tail":proc.stderr[-8000:],
            "adapter_development_parity_certified":False,
            "validation_base_matrix_execution_authorized":False,
            "validation_outcomes_opened":False,"final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_5_2_3_2_ADAPTER_EXECUTION_FAILURE"
        }
        atomic_json(resolve(root,a.output_json),report)
        shutil.rmtree(work,ignore_errors=True)
        print("=== M77.19.8.7.10.5.2.3.2 EXACT 8.2 PARTITION-LABEL & END PARAMETERIZATION DEVELOPMENT PARITY GATE ===")
        print("status: BLOCKED_8_2_PARTITION_LABEL_ADAPTER_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("report:",resolve(root,a.output_json))
        return 0

    expf,actf,erows,arows,missing,extra,mismatch=compare_dirs(resolve(root,a.certified_development_root),out_root)
    parity_ok=(
        expf==EXPECTED_DEV_SYMBOLS and actf==EXPECTED_DEV_SYMBOLS and
        erows==EXPECTED_DEV_ROWS and arows==EXPECTED_DEV_ROWS and
        not missing and not extra and not mismatch
    )
    status="READY" if parity_ok else "BLOCKED_8_2_PARTITION_LABEL_ADAPTER_DEVELOPMENT_PARITY_MISMATCH"

    report={
        "version":VERSION,"status":status,
        "forensics_sha256":sha256_file(forensic_path),
        "source_script_sha256":sha256_file(source),
        "adapter_script_sha256":sha256_file(adapter_script),
        "parameterization_scope":"PARTITION_END_AND_PARTITION_LABEL_ONLY",
        "development_partition_end_used":DEV_END,
        "development_partition_label_used":DEV_PARTITION,
        "operative_gate":"as_of<=DEV_END and r.get('partition')==ACTIVE_PARTITION_LABEL",
        "expected_symbol_file_count":expf,"actual_symbol_file_count":actf,
        "expected_row_count":erows,"actual_row_count":arows,
        "missing_symbol_files":missing,"extra_symbol_files":extra,
        "mismatch_symbol_count":len(mismatch),"mismatch_symbols":mismatch,
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
            "BUILD_M77_19_8_7_10_5_2_3_3_EXACT_8_2_VALIDATION_PARTITION_BASE_MATRIX_MATERIALIZATION"
            if parity_ok else
            "REVIEW_M77_19_8_7_10_5_2_3_2_DEVELOPMENT_PARITY_MISMATCH"
        )
    }
    if parity_ok:
        dst=root/"scripts/run_m77_19_8_2_partition_label_end_parameterized_certified.py"
        shutil.copy2(adapter_script,dst)
        report["certified_adapter_script"]=str(dst.relative_to(root))
        report["certified_adapter_script_sha256"]=sha256_file(dst)

    atomic_json(resolve(root,a.output_json),report)
    shutil.rmtree(work,ignore_errors=True)

    print("=== M77.19.8.7.10.5.2.3.2 EXACT 8.2 PARTITION-LABEL & END PARAMETERIZATION DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("parameterization_scope: PARTITION_END_AND_PARTITION_LABEL_ONLY")
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

if __name__=="__main__":raise SystemExit(main())
