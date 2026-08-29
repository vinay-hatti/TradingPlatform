#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, csv, hashlib, json, os, tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.3-MF2-MAIN-CALL-GRAPH-SOLVER-EXTRACTION-FORENSICS-1.0"

class ForensicsError(RuntimeError):
    pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

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
        return ast.get_source_segment(text,node) or ""
    except Exception:
        return ""

def call_name(node):
    if isinstance(node,ast.Name):
        return node.id
    if isinstance(node,ast.Attribute):
        parts=[]
        cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr)
            cur=cur.value
        if isinstance(cur,ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""

def analyze(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)

    top_funcs={}
    nested_funcs=[]
    main_node=None
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            top_funcs[node.name]=node
            if node.name=="main":
                main_node=node

    if main_node is None:
        raise ForensicsError("MF2 Development script has no main()")

    # Find nested/local functions reachable inside main.
    for node in ast.walk(main_node):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node is not main_node:
            body=seg(text,node)
            low=body.lower()
            tags=[]
            for needle,tag in (
                ("spline","SPLINE"),
                ("monotonic","MONOTONIC"),
                ("lbfgsb","LBFGSB"),
                ("l-bfgs-b","LBFGSB"),
                ("minimize(","MINIMIZE"),
                ("scipy.optimize","SCIPY_OPTIMIZE"),
                ("balanced_accuracy","BALANCED_ACCURACY"),
                ("preprocess","PREPROCESS"),
                ("transform(","TRANSFORM"),
                ("fit(","FIT"),
                ("predict","PREDICT"),
                ("l2_penalty","L2_PENALTY"),
                ("spline_knots","SPLINE_KNOTS"),
            ):
                if needle in low:
                    tags.append(tag)
            nested_funcs.append({
                "name":node.name,
                "lineno":node.lineno,
                "end_lineno":getattr(node,"end_lineno",node.lineno),
                "args":[a.arg for a in node.args.args],
                "tags":sorted(set(tags)),
                "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
                "source_excerpt":body[:4000],
            })

    # Analyze every statement inside main for direct solver/model semantics.
    statement_evidence=[]
    direct_solver_lines=[]
    direct_model_semantics=[]
    for node in ast.walk(main_node):
        if isinstance(node,ast.Call):
            src=seg(text,node)
            low=src.lower()
            tags=[]
            for needle,tag in (
                ("minimize","MINIMIZE"),
                ("scipy.optimize","SCIPY_OPTIMIZE"),
                ("lbfgsb","LBFGSB"),
                ("l-bfgs-b","LBFGSB"),
                ("spline","SPLINE"),
                ("monotonic","MONOTONIC"),
                ("balanced_accuracy","BALANCED_ACCURACY"),
                ("predict","PREDICT"),
                ("fit","FIT"),
                ("transform","TRANSFORM"),
            ):
                if needle in low:
                    tags.append(tag)
            if tags:
                ev={
                    "lineno":node.lineno,
                    "call_name":call_name(node.func),
                    "tags":sorted(set(tags)),
                    "source":src[:3000],
                }
                statement_evidence.append(ev)
                if set(tags) & {"MINIMIZE","SCIPY_OPTIMIZE","LBFGSB","SPLINE","MONOTONIC"}:
                    direct_solver_lines.append(node.lineno)
                    direct_model_semantics.append(ev)

    # Assignments carrying frozen MF2 config or solver artifacts.
    assignments=[]
    for node in ast.walk(main_node):
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            src=seg(text,node)
            low=src.lower()
            tags=[]
            for needle,tag in (
                ("l2_penalty","L2_PENALTY"),
                ("spline_knots","SPLINE_KNOTS"),
                ("selected_config","SELECTED_CONFIG"),
                ("knots","KNOTS"),
                ("coef","COEFFICIENTS"),
                ("weights","WEIGHTS"),
                ("design","DESIGN_MATRIX"),
                ("basis","SPLINE_BASIS"),
                ("objective","OBJECTIVE"),
            ):
                if needle in low:
                    tags.append(tag)
            if tags:
                assignments.append({
                    "lineno":node.lineno,
                    "tags":sorted(set(tags)),
                    "source":src[:3000],
                })

    # Calls from main to top-level helper functions, preserving call order.
    main_calls=[]
    for node in ast.walk(main_node):
        if isinstance(node,ast.Call):
            nm=call_name(node.func)
            base=nm.split(".")[-1]
            if base in top_funcs and base!="main":
                main_calls.append({
                    "lineno":node.lineno,
                    "callee":base,
                    "callee_lineno":top_funcs[base].lineno,
                    "source":seg(text,node)[:2000],
                })
    main_calls=sorted(main_calls,key=lambda x:x["lineno"])

    # Candidate code regions: nested function or direct main block.
    nested_solver_candidates=[
        x for x in nested_funcs
        if set(x["tags"]) & {"MONOTONIC","SPLINE","LBFGSB","MINIMIZE","SCIPY_OPTIMIZE"}
    ]

    classification = None
    if nested_solver_candidates:
        classification="MF2_MODEL_LOGIC_IN_NESTED_MAIN_LOCAL_CALLABLES"
    elif direct_model_semantics:
        classification="MF2_MODEL_LOGIC_INLINE_INSIDE_MAIN"
    elif main_calls:
        classification="MF2_MODEL_LOGIC_POSSIBLY_TOP_LEVEL_HELPER_CHAIN_NOT_TAGGED_DIRECTLY"
    else:
        classification="MF2_MODEL_LOGIC_NOT_LOCATED"

    return {
        "script_sha256":sha256_file(path),
        "main_lineno":main_node.lineno,
        "main_end_lineno":getattr(main_node,"end_lineno",main_node.lineno),
        "nested_function_count":len(nested_funcs),
        "nested_functions":nested_funcs,
        "nested_solver_candidates":nested_solver_candidates,
        "direct_model_semantic_calls":direct_model_semantics,
        "direct_solver_line_numbers":sorted(set(direct_solver_lines)),
        "main_to_top_level_helper_calls":main_calls,
        "model_related_assignments":assignments,
        "classification":classification,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-parity-json",default="reports/m77_19_8_7_10_7_2_exact_mf1_mf2_callable_invocation_contract_development_parity_harness.json")
    ap.add_argument("--reuse-binding-json",default="reports/m77_19_8_7_10_7_1_frozen_development_model_preprocessor_implementation_reuse_binding_authority.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-runtime-script",default="scripts/run_m77_19_8_7_4_mf2_runtime_mf3_elastic_net_quantile_solver_certification.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_3_mf2_main_call_graph_solver_extraction_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_3_mf2_solver_candidate_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    failed=load_json(resolve(root,args.failed_parity_json))
    binding=load_json(resolve(root,args.reuse_binding_json))
    if binding.get("status")!="READY":
        raise ForensicsError("10.7.1 reuse binding not READY")
    if binding.get("validation_scoring_performed") is not False:
        raise ForensicsError("Validation scoring already performed")
    if binding.get("final_holdout_opened") is not False:
        raise ForensicsError("Final Holdout already opened")

    mf2p=resolve(root,args.mf2_development_script)
    runtimep=resolve(root,args.mf2_runtime_script)
    if not mf2p.exists() or not runtimep.exists():
        raise ForensicsError("required MF2 source script missing")

    dev=analyze(mf2p)
    runtime=analyze(runtimep)

    rows=[]
    for c in dev["nested_solver_candidates"]:
        rows.append({
            "source":"MF2_DEVELOPMENT",
            "candidate_type":"NESTED_FUNCTION",
            "name":c["name"],
            "lineno":c["lineno"],
            "end_lineno":c["end_lineno"],
            "tags":"|".join(c["tags"]),
            "source_sha256":c["source_sha256"],
        })
    for c in dev["direct_model_semantic_calls"]:
        rows.append({
            "source":"MF2_DEVELOPMENT",
            "candidate_type":"INLINE_MAIN_CALL",
            "name":c["call_name"],
            "lineno":c["lineno"],
            "end_lineno":c["lineno"],
            "tags":"|".join(c["tags"]),
            "source_sha256":hashlib.sha256(c["source"].encode()).hexdigest(),
        })
    for c in runtime["nested_solver_candidates"]:
        rows.append({
            "source":"MF2_RUNTIME",
            "candidate_type":"NESTED_FUNCTION",
            "name":c["name"],
            "lineno":c["lineno"],
            "end_lineno":c["end_lineno"],
            "tags":"|".join(c["tags"]),
            "source_sha256":c["source_sha256"],
        })
    for c in runtime["direct_model_semantic_calls"]:
        rows.append({
            "source":"MF2_RUNTIME",
            "candidate_type":"INLINE_MAIN_CALL",
            "name":c["call_name"],
            "lineno":c["lineno"],
            "end_lineno":c["lineno"],
            "tags":"|".join(c["tags"]),
            "source_sha256":hashlib.sha256(c["source"].encode()).hexdigest(),
        })

    located=dev["classification"]!="MF2_MODEL_LOGIC_NOT_LOCATED"
    status="READY" if located else "BLOCKED_MF2_MODEL_LOGIC_NOT_LOCATED"

    report={
        "version":VERSION,
        "status":status,
        "failed_parity_report_status":failed.get("status"),
        "failed_parity_sha256":sha256_file(resolve(root,args.failed_parity_json)),
        "reuse_binding_sha256":sha256_file(resolve(root,args.reuse_binding_json)),
        "MF2_development_analysis":dev,
        "MF2_runtime_analysis":runtime,
        "root_cause_certified":located,
        "root_cause":dev["classification"],
        "MF2_model_logic_exposed_as_certifiable_top_level_callable":False,
        "MF2_exact_solver_extraction_authorized":located,
        "MF2_formula_reimplementation_authorized":False,
        "MF2_semantic_equivalent_rewrite_authorized":False,
        "validation_scoring_execution_authorized":False,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_4_EXACT_MF2_SOLVER_CALL_GRAPH_EXTRACTION_AND_DEVELOPMENT_PARITY_GATE"
            if located else
            "REVIEW_M77_19_8_7_10_7_2_3_MF2_MODEL_LOGIC_LOCATION_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["source","candidate_type","name","lineno","end_lineno","tags","source_sha256"]
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print("=== M77.19.8.7.10.7.2.3 MF2 MAIN CALL-GRAPH & SOLVER EXTRACTION FORENSICS ===")
    print("status:",status)
    print("MF2_development_script_sha256:",dev["script_sha256"])
    print("MF2_main_lineno:",dev["main_lineno"])
    print("MF2_main_end_lineno:",dev["main_end_lineno"])
    print("MF2_nested_function_count:",dev["nested_function_count"])
    print("MF2_nested_solver_candidate_count:",len(dev["nested_solver_candidates"]))
    print("MF2_direct_model_semantic_call_count:",len(dev["direct_model_semantic_calls"]))
    print("MF2_top_level_helper_call_count:",len(dev["main_to_top_level_helper_calls"]))
    print("MF2_model_related_assignment_count:",len(dev["model_related_assignments"]))
    print("root_cause_certified:",located)
    print("root_cause:",dev["classification"])
    for i,c in enumerate(dev["nested_solver_candidates"][:10],1):
        print(f"nested_candidate_{i}: name={c['name']} line={c['lineno']} tags={c['tags']}")
    for i,c in enumerate(dev["direct_model_semantic_calls"][:20],1):
        print(f"inline_candidate_{i}: call={c['call_name']} line={c['lineno']} tags={c['tags']}")
    print("MF2_exact_solver_extraction_authorized:",located)
    print("MF2_formula_reimplementation_authorized: False")
    print("MF2_semantic_equivalent_rewrite_authorized: False")
    print("validation_scoring_execution_authorized: False")
    print("validation_scoring_performed: False")
    print("validation_preprocessor_refit_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("model_family_champion_selected: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
