#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.3-EXACT-IMPLEMENTATION-REUSE-BINDING-AUTHORITY-1.0"
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")
class BindingError(RuntimeError): pass

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
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def source_segment(lines,node):
    return "\n".join(lines[node.lineno-1:getattr(node,"end_lineno",node.lineno)])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--continuity-authority-json",default="reports/m77_19_8_7_10_2_exact_validation_backfill_source_resolver_feature_continuity_authority.json")
    ap.add_argument("--development-backfill-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_3_exact_implementation_reuse_binding_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_3_feature_implementation_binding_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cp=resolve(root,a.continuity_authority_json);sp=resolve(root,a.development_backfill_script)
    c=load_json(cp)
    if c.get("status")!="READY" or c.get("exact_validation_source_continuity_certified") is not True:
        raise BindingError("10.2 continuity authority is not READY/certified")
    if c.get("validation_outcomes_opened") is not False or c.get("final_holdout_opened") is not False:
        raise BindingError("partition governance violated")
    certified_sha=c.get("development_backfill_script_sha256")
    actual_sha=sha256_file(sp)
    if certified_sha!=actual_sha:raise BindingError("8.4.3 implementation SHA changed after 10.2 certification")

    text=sp.read_text(encoding="utf-8");lines=text.splitlines();tree=ast.parse(text)
    functions=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    assignments=[n for n in ast.walk(tree) if isinstance(n,(ast.Assign,ast.AnnAssign))]
    registry=[]
    all_bound=True

    for fid in REQUIRED_FEATURE_IDS:
        matches=[]
        for fn in functions:
            seg=source_segment(lines,fn)
            if fid in seg:
                matches.append({
                    "kind":"FUNCTION","name":fn.name,"lineno":fn.lineno,
                    "end_lineno":getattr(fn,"end_lineno",fn.lineno),
                    "segment_sha256":hashlib.sha256(seg.encode()).hexdigest()
                })
        for node in assignments:
            seg=source_segment(lines,node)
            if fid in seg:
                matches.append({
                    "kind":"ASSIGNMENT","name":"<assignment>","lineno":node.lineno,
                    "end_lineno":getattr(node,"end_lineno",node.lineno),
                    "segment_sha256":hashlib.sha256(seg.encode()).hexdigest()
                })
        # Exact reuse is considered directly callable only when at least one function
        # contains the feature implementation. Assignment-only evidence requires an
        # extraction/refactor gate before Validation materialization.
        fn_matches=[m for m in matches if m["kind"]=="FUNCTION"]
        status="DIRECT_CALLABLE_BINDING_FOUND" if fn_matches else ("INLINE_IMPLEMENTATION_REQUIRES_EXACT_EXTRACTION" if matches else "IMPLEMENTATION_BINDING_NOT_FOUND")
        if status!="DIRECT_CALLABLE_BINDING_FOUND":all_bound=False
        registry.append({"feature_id":fid,"binding_status":status,"match_count":len(matches),"matches":matches})

    report={
        "version":VERSION,"status":"READY" if all_bound else "BLOCKED_EXACT_IMPLEMENTATION_BINDING",
        "continuity_authority_sha256":sha256_file(cp),
        "development_backfill_script_sha256":actual_sha,
        "required_feature_ids":list(REQUIRED_FEATURE_IDS),
        "feature_bindings":registry,
        "all_required_features_directly_callable":all_bound,
        "formula_reimplementation_authorized":False,
        "semantic_equivalent_rewrite_authorized":False,
        "inline_code_extraction_authorized_by_this_step":False,
        "validation_feature_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_4_EXACT_CALLABLE_REUSE_VALIDATION_FEATURE_MATERIALIZATION"
            if all_bound else
            "BUILD_M77_19_8_7_10_3_1_EXACT_INLINE_IMPLEMENTATION_EXTRACTION_AND_PARITY_AUTHORITY"
        ),
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    flat=[]
    for r in registry:
        flat.append({"feature_id":r["feature_id"],"binding_status":r["binding_status"],"match_count":r["match_count"],"matches_json":json.dumps(r["matches"],sort_keys=True)})
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)

    print("=== M77.19.8.7.10.3 EXACT IMPLEMENTATION-REUSE BINDING AUTHORITY ===")
    print("status:",report["status"])
    print("development_backfill_script_sha256:",actual_sha)
    for r in registry:print(f"{r['feature_id']}: {r['binding_status']} matches={r['match_count']}")
    print("all_required_features_directly_callable:",all_bound)
    print("formula_reimplementation_authorized: False")
    print("semantic_equivalent_rewrite_authorized: False")
    print("validation_feature_matrix_materialized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
