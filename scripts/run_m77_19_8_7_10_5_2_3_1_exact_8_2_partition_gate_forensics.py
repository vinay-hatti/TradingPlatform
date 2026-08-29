#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, hashlib, json, os, tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.3.1-EXACT-8.2-PARTITION-GATE-FORENSICS-1.0"

class ForensicError(RuntimeError): pass

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

def src_segment(text,node):
    try:return ast.get_source_segment(text,node)
    except Exception:return None

def name_of(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):
        base=name_of(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None

def contains_partition_signal(node):
    for n in ast.walk(node):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            s=n.value.upper()
            if any(x in s for x in ("2017-12-31","2018-01-01","2022-12-31","DEVELOPMENT","VALIDATION")):
                return True
        if isinstance(n,ast.Name):
            s=n.id.upper()
            if any(x in s for x in ("DEV_END","DEVELOP","VALID","PARTITION","AS_OF")):
                return True
        if isinstance(n,ast.Attribute):
            s=n.attr.upper()
            if any(x in s for x in ("DEV_END","DEVELOP","VALID","PARTITION","AS_OF")):
                return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-validation-json",default="reports/m77_19_8_7_10_5_2_3_exact_8_2_validation_base_matrix_materialization.json")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_2_2_exact_8_2_base_matrix_partition_parameterization_development_parity_gate.json")
    ap.add_argument("--source-script",default="scripts/run_m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.py")
    ap.add_argument("--certified-adapter-script",default="scripts/run_m77_19_8_2_partition_parameterized_certified.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_3_1_exact_8_2_partition_gate_forensics.json")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    failed=load_json(resolve(root,a.failed_validation_json))
    auth=load_json(resolve(root,a.adapter_authority_json))
    source=resolve(root,a.source_script)
    adapter=resolve(root,a.certified_adapter_script)

    if failed.get("status")!="BLOCKED_VALIDATION_BASE_MATRIX_CERTIFICATION_FAILURE":
        raise ForensicError("10.5.2.3 not in expected blocked state")
    if failed.get("adapter_total_row_count")!=303689 or failed.get("validation_only_row_count")!=0:
        raise ForensicError("10.5.2.3 failure mode changed")
    if auth.get("status")!="READY" or auth.get("adapter_development_parity_certified") is not True:
        raise ForensicError("10.5.2.2 adapter authority not certified")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ForensicError("certified 8.2 adapter SHA changed")
    if failed.get("validation_outcomes_opened") is not False or failed.get("final_holdout_opened") is not False:
        raise ForensicError("partition governance violated")

    text=source.read_text(encoding="utf-8")
    atxt=adapter.read_text(encoding="utf-8")
    tree=ast.parse(text)
    atree=ast.parse(atxt)

    constants=[]
    assignments=[]
    gates=[]
    calls=[]

    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            s=n.value
            if any(x in s.upper() for x in ("2017-12-31","2018-01-01","2022-12-31","DEVELOPMENT","VALIDATION")):
                constants.append({"value":s,"lineno":getattr(n,"lineno",None)})

        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=[]
            if isinstance(n,ast.Assign):
                targets=[name_of(x) for x in n.targets]
            else:
                targets=[name_of(n.target)]
            if contains_partition_signal(n):
                assignments.append({
                    "targets":[x for x in targets if x],
                    "lineno":getattr(n,"lineno",None),
                    "end_lineno":getattr(n,"end_lineno",getattr(n,"lineno",None)),
                    "source":src_segment(text,n),
                })

        if isinstance(n,(ast.If,ast.IfExp,ast.Assert,ast.comprehension)):
            test = n.test if hasattr(n,"test") else n
            if contains_partition_signal(test):
                gates.append({
                    "kind":type(n).__name__,
                    "lineno":getattr(n,"lineno",None),
                    "end_lineno":getattr(n,"end_lineno",getattr(n,"lineno",None)),
                    "source":src_segment(text,n),
                    "test_source":src_segment(text,test),
                })

        if isinstance(n,ast.Call) and contains_partition_signal(n):
            calls.append({
                "callee":name_of(n.func),
                "lineno":getattr(n,"lineno",None),
                "source":src_segment(text,n),
            })

    # Adapter-specific evidence: identify runtime DEV_END override and whether
    # other Development gates remain unchanged.
    adapter_dev_end_refs=[]
    adapter_development_literals=[]
    for n in ast.walk(atree):
        if isinstance(n,ast.Name) and n.id=="DEV_END":
            adapter_dev_end_refs.append(getattr(n,"lineno",None))
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and "DEVELOPMENT" in n.value.upper():
            adapter_development_literals.append({"value":n.value,"lineno":getattr(n,"lineno",None)})

    # Rank likely operative gates. Exact evidence only; no mutation.
    likely=[]
    for g in gates:
        src=(g.get("test_source") or "").upper()
        score=0
        reasons=[]
        if "DEVELOPMENT" in src:
            score+=5;reasons.append("REFERENCES_DEVELOPMENT_LITERAL_OR_STATE")
        if "DEV_END" in src:
            score+=3;reasons.append("REFERENCES_DEV_END")
        if "AS_OF" in src:
            score+=3;reasons.append("REFERENCES_AS_OF")
        if "PARTITION" in src:
            score+=4;reasons.append("REFERENCES_PARTITION")
        if score:
            likely.append({**g,"forensic_score":score,"reasons":reasons})
    likely=sorted(likely,key=lambda x:(-x["forensic_score"],x.get("lineno") or 0))

    report={
        "version":VERSION,
        "status":"READY",
        "source_script_sha256":sha256_file(source),
        "certified_adapter_script_sha256":sha256_file(adapter),
        "failed_adapter_total_row_count":failed.get("adapter_total_row_count"),
        "failed_adapter_last_as_of":failed.get("adapter_last_as_of"),
        "failed_validation_only_row_count":failed.get("validation_only_row_count"),
        "partition_signal_constants":constants,
        "partition_signal_assignments":assignments,
        "partition_signal_gates":gates,
        "partition_signal_calls":calls,
        "ranked_likely_partition_gates":likely,
        "certified_adapter_dev_end_reference_lines":sorted(set(x for x in adapter_dev_end_refs if x is not None)),
        "certified_adapter_development_literals":adapter_development_literals,
        "feature_matrix_mutated":False,
        "feature_formula_change_authorized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":"REVIEW_M77_19_8_7_10_5_2_3_1_EXACT_PARTITION_GATE_EVIDENCE_BEFORE_PARAMETERIZATION"
    }
    atomic_json(resolve(root,a.output_json),report)

    print("=== M77.19.8.7.10.5.2.3.1 EXACT 8.2 PARTITION-GATE FORENSICS ===")
    print("status: READY")
    print("source_script_sha256:",report["source_script_sha256"])
    print("certified_adapter_script_sha256:",report["certified_adapter_script_sha256"])
    print("failed_adapter_total_row_count:",report["failed_adapter_total_row_count"])
    print("failed_adapter_last_as_of:",report["failed_adapter_last_as_of"])
    print("failed_validation_only_row_count:",report["failed_validation_only_row_count"])
    print("partition_signal_constant_count:",len(constants))
    print("partition_signal_assignment_count:",len(assignments))
    print("partition_signal_gate_count:",len(gates))
    print("partition_signal_call_count:",len(calls))
    print("ranked_likely_partition_gate_count:",len(likely))
    for i,g in enumerate(likely[:20],1):
        print(f"likely_gate_{i}: line={g.get('lineno')} score={g.get('forensic_score')} reasons={g.get('reasons')}")
        print("  test:",g.get("test_source"))
    print("certified_adapter_dev_end_reference_lines:",report["certified_adapter_dev_end_reference_lines"])
    print("feature_matrix_mutated: False")
    print("feature_formula_change_authorized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
