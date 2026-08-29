#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5.2.4.3-EXACT-8.4.3-VALIDATION-ROW-ADMISSION-FORENSICS-1.0"

class ForensicsError(RuntimeError): pass

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

def seg(text,node):
    try:
        return ast.get_source_segment(text,node)
    except Exception:
        return None

def relevant(node):
    for n in ast.walk(node):
        if isinstance(n,ast.Name):
            u=n.id.upper()
            if any(x in u for x in ("DEV_END","PARTITION","AS_OF","TOTAL_ROWS","MATRIX","VALIDATION")):
                return True
        if isinstance(n,ast.Attribute):
            u=n.attr.upper()
            if any(x in u for x in ("DEV_END","PARTITION","AS_OF","TOTAL_ROWS","MATRIX","VALIDATION")):
                return True
        if isinstance(n,ast.Constant) and isinstance(n.value,(str,int)):
            s=str(n.value).upper()
            if any(x in s for x in ("2017-12-31","2018-01-01","2022-12-31","DEVELOPMENT","VALIDATION","303689","141567")):
                return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-validation-json",default="reports/m77_19_8_7_10_5_2_4_exact_8_4_3_validation_backfill_matrix_materialization.json")
    ap.add_argument("--adapter-authority-json",default="reports/m77_19_8_7_10_5_2_4_1_exact_8_4_3_input_cardinality_parameterization_development_parity_gate.json")
    ap.add_argument("--adapter-script",default="scripts/run_m77_19_8_4_3_cardinality_parameterized_certified.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_2_4_3_exact_8_4_3_validation_row_admission_forensics.json")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    failed=load_json(resolve(root,args.failed_validation_json))
    auth=load_json(resolve(root,args.adapter_authority_json))
    adapter=resolve(root,args.adapter_script)

    if failed.get("status")!="BLOCKED_VALIDATION_BACKFILL_EXECUTION_FAILED":
        raise ForensicsError("10.5.2.4 not in expected blocked state")
    stderr=failed.get("stderr_tail") or ""
    if "Development row count changed: 0" not in stderr:
        raise ForensicsError("10.5.2.4 failure mode changed")
    if auth.get("status")!="READY" or auth.get("development_parity_certified") is not True:
        raise ForensicsError("10.5.2.4.1 authority not READY/certified")
    if sha256_file(adapter)!=auth.get("certified_adapter_script_sha256"):
        raise ForensicsError("certified adapter SHA changed")
    if failed.get("validation_outcomes_opened") is not False or failed.get("final_holdout_opened") is not False:
        raise ForensicsError("governance violation")

    text=adapter.read_text(encoding="utf-8")
    tree=ast.parse(text)

    total_row_refs=[]
    relevant_ifs=[]
    relevant_assignments=[]
    relevant_calls=[]
    raises=[]

    for node in ast.walk(tree):
        if isinstance(node,ast.Name) and node.id=="total_rows":
            total_row_refs.append({
                "lineno":getattr(node,"lineno",None),
                "ctx":type(node.ctx).__name__,
            })
        if isinstance(node,ast.If) and relevant(node.test):
            relevant_ifs.append({
                "lineno":node.lineno,
                "end_lineno":getattr(node,"end_lineno",node.lineno),
                "test":seg(text,node.test),
                "source":seg(text,node),
            })
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)) and relevant(node):
            relevant_assignments.append({
                "lineno":getattr(node,"lineno",None),
                "end_lineno":getattr(node,"end_lineno",getattr(node,"lineno",None)),
                "source":seg(text,node),
            })
        if isinstance(node,ast.Call) and relevant(node):
            relevant_calls.append({
                "lineno":getattr(node,"lineno",None),
                "source":seg(text,node),
            })
        if isinstance(node,ast.Raise):
            s=seg(text,node) or ""
            if "Development row count changed" in s or "total_rows" in s:
                raises.append({
                    "lineno":node.lineno,
                    "source":s,
                })

    # Capture a focused source window around the failing row-count raise.
    fail_lines=[x["lineno"] for x in raises if x.get("lineno")]
    if not fail_lines:
        # fallback to literal search
        for i,line in enumerate(text.splitlines(),1):
            if "Development row count changed" in line:
                fail_lines.append(i)
    if not fail_lines:
        raise ForensicsError("failing Development row-count guard not found")

    lines=text.splitlines()
    center=fail_lines[0]
    start=max(1,center-80)
    end=min(len(lines),center+20)
    source_window=[
        {"lineno":i,"source":lines[i-1]}
        for i in range(start,end+1)
    ]

    # Rank row-admission gates appearing before the failing total-row assertion.
    candidates=[]
    for item in relevant_ifs:
        if item["lineno"] >= center:
            continue
        test=(item.get("test") or "")
        u=test.upper()
        score=0
        reasons=[]
        if "DEV_END" in u:
            score+=5; reasons.append("REFERENCES_DEV_END")
        if "PARTITION" in u:
            score+=5; reasons.append("REFERENCES_PARTITION")
        if "AS_OF" in u:
            score+=4; reasons.append("REFERENCES_AS_OF")
        if "VALIDATION" in u:
            score+=4; reasons.append("REFERENCES_VALIDATION")
        if "DEVELOPMENT" in u:
            score+=4; reasons.append("REFERENCES_DEVELOPMENT")
        if "CONTINUE" in (item.get("source") or "").upper():
            score+=3; reasons.append("CAN_SKIP_ROW")
        if score:
            candidates.append({**item,"score":score,"reasons":reasons})
    candidates=sorted(candidates,key=lambda x:(-x["score"],-x["lineno"]))

    report={
        "version":VERSION,
        "status":"READY",
        "failed_validation_sha256":sha256_file(resolve(root,args.failed_validation_json)),
        "adapter_authority_sha256":sha256_file(resolve(root,args.adapter_authority_json)),
        "certified_adapter_script_sha256":sha256_file(adapter),
        "failure_signature":"DEVELOPMENT_ROW_COUNT_CHANGED_ZERO",
        "failing_row_count_guard_lines":fail_lines,
        "total_rows_reference_count":len(total_row_refs),
        "total_rows_references":total_row_refs,
        "relevant_if_count":len(relevant_ifs),
        "relevant_assignment_count":len(relevant_assignments),
        "relevant_call_count":len(relevant_calls),
        "ranked_row_admission_gate_candidates":candidates,
        "focused_source_window":source_window,
        "feature_matrix_mutated":False,
        "feature_formula_change_authorized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":"REVIEW_M77_19_8_7_10_5_2_4_3_ROW_ADMISSION_EVIDENCE_BEFORE_PARAMETERIZATION",
    }
    atomic_json(resolve(root,args.output_json),report)

    print("=== M77.19.8.7.10.5.2.4.3 EXACT 8.4.3 VALIDATION ROW-ADMISSION FORENSICS ===")
    print("status: READY")
    print("failure_signature: DEVELOPMENT_ROW_COUNT_CHANGED_ZERO")
    print("certified_adapter_script_sha256:",report["certified_adapter_script_sha256"])
    print("failing_row_count_guard_lines:",fail_lines)
    print("total_rows_reference_count:",len(total_row_refs))
    print("ranked_row_admission_gate_candidate_count:",len(candidates))
    for i,c in enumerate(candidates[:20],1):
        print(f"candidate_{i}: line={c['lineno']} score={c['score']} reasons={c['reasons']}")
        print("  test:",c.get("test"))
    print("focused_source_window:")
    for row in source_window:
        print(f"{row['lineno']:4d}: {row['source']}")
    print("feature_matrix_mutated: False")
    print("feature_formula_change_authorized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
