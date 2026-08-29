#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,gzip,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.1-VALIDATION-BASE-MATRIX-PARTITION-COUPLING-FORENSICS-1.0"
DEV_ROWS=303689
DEV_SYMBOLS=524
VAL_ROWS=141567
VAL_SYMBOLS=570

class ForensicError(RuntimeError):pass

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
def count_jsonl_dir(root):
    files=sorted(Path(root).glob("*.jsonl.gz"))
    rows=0
    for p in files:
        with gzip.open(p,"rt",encoding="utf-8") as f:
            for line in f:
                if line.strip():rows+=1
    return len(files),rows
def call_name(n):
    if isinstance(n,ast.Name):return n.id
    if isinstance(n,ast.Attribute):
        b=call_name(n.value);return f"{b}.{n.attr}" if b else n.attr
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-validation-json",default="reports/m77_19_8_7_10_5_2_exact_adapter_validation_feature_matrix_materialization.json")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_1_exact_8_4_3_partition_parameterization_adapter_development_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_4_3_partition_parameterized_certified.py")
    ap.add_argument("--development-base-matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--development-base-matrix-script",default="scripts/run_m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.py")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_1_validation_base_matrix_partition_coupling_forensics.json")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    failed=load_json(resolve(root,a.failed_validation_json))
    auth=load_json(resolve(root,a.adapter_authority_json))
    adapter=resolve(root,a.adapter_script)
    base_root=resolve(root,a.development_base_matrix_root)
    base_script=resolve(root,a.development_base_matrix_script)

    if failed.get("status")!="BLOCKED_VALIDATION_FEATURE_MATRIX_CERTIFICATION_FAILURE":
        raise ForensicError("10.5.2 is not in expected blocked certification state")
    if failed.get("validation_symbol_count")!=DEV_SYMBOLS or failed.get("validation_row_count")!=DEV_ROWS:
        raise ForensicError("10.5.2 did not reproduce exact Development cardinality; different failure mode")
    if auth.get("status")!="READY" or auth.get("adapter_development_parity_certified") is not True:
        raise ForensicError("10.5.1 adapter authority not certified")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ForensicError("certified adapter SHA changed")
    if not base_script.exists():
        raise ForensicError(f"8.2 base matrix script missing: {base_script}")

    base_files,base_rows=count_jsonl_dir(base_root)
    if base_files!=DEV_SYMBOLS or base_rows!=DEV_ROWS:
        raise ForensicError(f"Development base matrix authority changed: files={base_files} rows={base_rows}")

    adapter_text=adapter.read_text(encoding="utf-8")
    base_text=base_script.read_text(encoding="utf-8")
    adapter_tree=ast.parse(adapter_text)
    base_tree=ast.parse(base_text)

    matrix_root_cli=False
    for n in ast.walk(adapter_tree):
        if isinstance(n,ast.Call) and call_name(n.func).endswith("add_argument"):
            if any(isinstance(x,ast.Constant) and x.value=="--matrix-root" for x in n.args):
                matrix_root_cli=True

    dev_literals=[]
    partition_terms=[]
    for n in ast.walk(base_tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            s=n.value
            if "2017-12-31" in s or "DEVELOPMENT" in s or "VALIDATION" in s:
                dev_literals.append({"value":s,"lineno":getattr(n,"lineno",None)})
        if isinstance(n,ast.Name) and any(t in n.id.lower() for t in ("develop","valid","partition")):
            partition_terms.append(n.id)

    replay_profiles=resolve(root,a.replay_root)/"weekly"/"profiles"
    val_symbols=set();val_rows=0
    for p in sorted(replay_profiles.glob("*.jsonl.gz")):
        c=0
        with gzip.open(p,"rt",encoding="utf-8") as f:
            for line in f:
                if not line.strip():continue
                r=json.loads(line)
                d=str(r.get("as_of") or "")[:10]
                if r.get("status")=="REPLAYED" and "2018-01-01"<=d<="2022-12-31":
                    c+=1
        if c:
            val_symbols.add(p.name[:-9]);val_rows+=c

    conclusion=(
        matrix_root_cli and base_files==DEV_SYMBOLS and base_rows==DEV_ROWS and
        len(val_symbols)==VAL_SYMBOLS and val_rows==VAL_ROWS
    )

    report={
        "version":VERSION,
        "status":"READY" if conclusion else "BLOCKED_FORENSIC_INCONCLUSIVE",
        "failed_validation_cardinality":{"symbols":failed.get("validation_symbol_count"),"rows":failed.get("validation_row_count")},
        "development_base_matrix_cardinality":{"symbols":base_files,"rows":base_rows},
        "validation_replay_cardinality":{"symbols":len(val_symbols),"rows":val_rows},
        "certified_adapter_accepts_matrix_root":matrix_root_cli,
        "development_base_matrix_script":str(base_script.relative_to(root)),
        "development_base_matrix_script_sha256":sha256_file(base_script),
        "base_matrix_partition_literals":dev_literals,
        "base_matrix_partition_identifier_count":len(set(partition_terms)),
        "base_matrix_partition_identifiers":sorted(set(partition_terms)),
        "root_cause_certified":conclusion,
        "root_cause":"CERTIFIED_8_4_3_ADAPTER_RECEIVED_DEVELOPMENT_ONLY_8_2_BASE_MATRIX" if conclusion else None,
        "feature_formula_change_authorized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_2_2_EXACT_8_2_BASE_MATRIX_PARTITION_PARAMETERIZATION_AND_DEVELOPMENT_PARITY_GATE"
            if conclusion else
            "REVIEW_M77_19_8_7_10_5_2_1_FORENSIC_INCONCLUSIVE"
        )
    }
    atomic_json(resolve(root,a.output_json),report)

    print("=== M77.19.8.7.10.5.2.1 VALIDATION BASE-MATRIX PARTITION COUPLING FORENSICS ===")
    print("status:",report["status"])
    print("failed_validation_cardinality:",report["failed_validation_cardinality"])
    print("development_base_matrix_cardinality:",report["development_base_matrix_cardinality"])
    print("validation_replay_cardinality:",report["validation_replay_cardinality"])
    print("certified_adapter_accepts_matrix_root:",matrix_root_cli)
    print("development_base_matrix_script_sha256:",report["development_base_matrix_script_sha256"])
    print("base_matrix_partition_literals:",dev_literals)
    print("root_cause_certified:",conclusion)
    print("root_cause:",report["root_cause"])
    print("feature_formula_change_authorized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json))
    return 0

if __name__=="__main__":raise SystemExit(main())
