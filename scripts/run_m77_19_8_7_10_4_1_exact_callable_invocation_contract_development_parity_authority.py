#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,csv,gzip,hashlib,importlib.util,inspect,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.4.1-EXACT-CALLABLE-INVOCATION-CONTRACT-DEVELOPMENT-PARITY-AUTHORITY-1.0"
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")
EXPECTED_DEVELOPMENT_ROWS=303689

class ParityError(RuntimeError):pass

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

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ParityError(f"{path}:{i}: invalid JSONL") from exc

def import_module(path):
    spec=importlib.util.spec_from_file_location("m77_exact_8_4_3_for_parity",path)
    if spec is None or spec.loader is None:raise ParityError("cannot import exact 8.4.3 implementation")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def call_name(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):
        base=call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None

def local_call_graph(tree):
    functions={n.name:n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    graph={}
    for name,node in functions.items():
        calls=[]
        for c in ast.walk(node):
            if isinstance(c,ast.Call):
                n=call_name(c.func)
                if n:calls.append(n)
        graph[name]=sorted(set(calls))
    return functions,graph

def reachable_from_main(graph):
    seen=set();stack=["main"]
    while stack:
        cur=stack.pop()
        if cur in seen:continue
        seen.add(cur)
        for n in graph.get(cur,[]):
            leaf=n.rsplit(".",1)[-1]
            if leaf in graph and leaf not in seen:stack.append(leaf)
    return seen

def source_segment(lines,node):
    return "\n".join(lines[node.lineno-1:getattr(node,"end_lineno",node.lineno)])

def feature_mentions(text):
    return [fid for fid in REQUIRED_FEATURE_IDS if fid in text]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--blocked-callable-json",default="reports/m77_19_8_7_10_4_exact_callable_reuse_validation_feature_materialization.json")
    ap.add_argument("--binding-authority-json",default="reports/m77_19_8_7_10_3_exact_implementation_reuse_binding_authority.json")
    ap.add_argument("--development-backfill-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_4_1_exact_callable_invocation_contract_development_parity_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_4_1_callable_contract_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    bp=resolve(root,a.blocked_callable_json)
    apath=resolve(root,a.binding_authority_json)
    sp=resolve(root,a.development_backfill_script)
    dev_root=resolve(root,a.development_feature_root)

    blocked=load_json(bp);binding=load_json(apath)
    if blocked.get("status")!="BLOCKED_CANDIDATE_CALLABLE_INVOCATION_PARITY_NOT_YET_CERTIFIED":
        raise ParityError("10.4 is not in expected governed blocked state")
    if blocked.get("validation_feature_matrix_materialized") is not False:
        raise ParityError("10.4 unexpectedly materialized Validation features")
    if blocked.get("validation_outcomes_opened") is not False or blocked.get("final_holdout_opened") is not False:
        raise ParityError("partition governance violated")
    if binding.get("status")!="READY" or binding.get("all_required_features_directly_callable") is not True:
        raise ParityError("10.3 binding authority invalid")
    if sha256_file(sp)!=binding.get("development_backfill_script_sha256"):
        raise ParityError("8.4.3 source SHA changed after binding certification")

    text=sp.read_text(encoding="utf-8");lines=text.splitlines();tree=ast.parse(text)
    functions,graph=local_call_graph(tree)
    reachable=reachable_from_main(graph)

    # Build exact source-level contract candidates from functions reachable from main.
    registry=[]
    feature_to_reachable_functions={fid:[] for fid in REQUIRED_FEATURE_IDS}
    for name in sorted(reachable):
        node=functions.get(name)
        if node is None:continue
        seg=source_segment(lines,node)
        mentions=feature_mentions(seg)
        if mentions:
            rec={
                "function_name":name,
                "lineno":node.lineno,
                "end_lineno":getattr(node,"end_lineno",node.lineno),
                "signature":None,
                "source_sha256":hashlib.sha256(seg.encode()).hexdigest(),
                "feature_ids":mentions,
                "calls":[x for x in graph.get(name,[]) if x.rsplit(".",1)[-1] in functions],
            }
            registry.append(rec)
            for fid in mentions:feature_to_reachable_functions[fid].append(name)

    mod=import_module(sp)
    for rec in registry:
        fn=getattr(mod,rec["function_name"],None)
        if callable(fn):rec["signature"]=str(inspect.signature(fn))

    missing=[fid for fid,names in feature_to_reachable_functions.items() if not names]
    if missing:
        raise ParityError(f"feature-producing reachable callable missing for {missing}")

    # Determine whether there is a non-main callable covering all seven features.
    row_candidates=[
        r for r in registry
        if r["function_name"]!="main" and set(r["feature_ids"])==set(REQUIRED_FEATURE_IDS)
    ]

    # Count and fingerprint frozen Development authority before any parity execution.
    dev_files=sorted(dev_root.glob("*.jsonl.gz"))
    if not dev_files:raise ParityError("certified Development feature matrix missing")
    dev_rows=0;schema=None;schema_mismatch=0
    for p in dev_files:
        for row in iter_jsonl_gz(p):
            dev_rows+=1
            keys=sorted((row.get("feature_values") or {}).keys())
            if schema is None:schema=keys
            elif keys!=schema:schema_mismatch+=1
    if dev_rows!=EXPECTED_DEVELOPMENT_ROWS:
        raise ParityError(f"Development row authority changed: {dev_rows}")
    if schema_mismatch:
        raise ParityError(f"Development schema mismatch rows={schema_mismatch}")

    # No invocation is attempted unless a non-main full-row callable exists.
    # This prevents reconstructing main's orchestration semantics from guesses.
    if not row_candidates:
        status="BLOCKED_NO_NON_MAIN_FULL_ROW_CALLABLE"
        invocation_certified=False
        parity_certified=False
        next_step="BUILD_M77_19_8_7_10_4_2_EXACT_MAIN_CALL_GRAPH_EXTRACTION_AND_DEVELOPMENT_PARITY_HARNESS"
        blocking="FEATURE_LOGIC_IS_DISTRIBUTED_ACROSS_MAIN_REACHABLE_HELPERS_NO_SINGLE_NON_MAIN_FULL_ROW_CALLABLE"
    else:
        # Even when a full-row callable exists, its argument construction/state must
        # be proven from main before calling it. Record candidate and require a harness.
        status="BLOCKED_FULL_ROW_CALLABLE_FOUND_ARGUMENT_BINDING_NOT_YET_CERTIFIED"
        invocation_certified=False
        parity_certified=False
        next_step="BUILD_M77_19_8_7_10_4_2_EXACT_MAIN_CALL_GRAPH_EXTRACTION_AND_DEVELOPMENT_PARITY_HARNESS"
        blocking="FULL_ROW_CALLABLE_EXISTS_BUT_MAIN_ARGUMENT_BINDING_AND_STATE_CONSTRUCTION_NOT_YET_CERTIFIED"

    report={
        "version":VERSION,
        "status":status,
        "blocked_callable_authority_sha256":sha256_file(bp),
        "binding_authority_sha256":sha256_file(apath),
        "development_backfill_script_sha256":sha256_file(sp),
        "main_source_sha256":next((r["source_sha256"] for r in registry if r["function_name"]=="main"),None),
        "main_reachable_local_functions":sorted(reachable),
        "feature_producing_reachable_function_registry":registry,
        "feature_to_reachable_functions":feature_to_reachable_functions,
        "non_main_full_row_callable_candidates":[r["function_name"] for r in row_candidates],
        "development_feature_row_count":dev_rows,
        "development_feature_schema_column_count":len(schema or []),
        "development_schema_mismatch_count":schema_mismatch,
        "exact_callable_invocation_contract_certified":invocation_certified,
        "development_parity_execution_performed":False,
        "development_parity_certified":parity_certified,
        "formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_feature_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "blocking_reason":blocking,
        "next_step":next_step,
    }

    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    flat=[]
    for r in registry:
        flat.append({
            "function_name":r["function_name"],
            "signature":r["signature"],
            "source_sha256":r["source_sha256"],
            "feature_ids":json.dumps(r["feature_ids"]),
            "calls":json.dumps(r["calls"]),
            "lineno":r["lineno"],
            "end_lineno":r["end_lineno"],
        })
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=list(flat[0]) if flat else ["function_name"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(flat)

    print("=== M77.19.8.7.10.4.1 EXACT CALLABLE INVOCATION CONTRACT & DEVELOPMENT PARITY AUTHORITY ===")
    print("status:",status)
    print("development_backfill_script_sha256:",sha256_file(sp))
    print("development_feature_row_count:",dev_rows)
    print("development_feature_schema_column_count:",len(schema or []))
    print("main_reachable_local_function_count:",len(reachable))
    for fid,names in feature_to_reachable_functions.items():
        print(f"{fid}: reachable_feature_functions={names}")
    print("non_main_full_row_callable_candidates:",[r["function_name"] for r in row_candidates])
    print("exact_callable_invocation_contract_certified: False")
    print("development_parity_execution_performed: False")
    print("development_parity_certified: False")
    print("formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_feature_matrix_materialized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("blocking_reason:",blocking)
    print("next_step:",next_step)
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
