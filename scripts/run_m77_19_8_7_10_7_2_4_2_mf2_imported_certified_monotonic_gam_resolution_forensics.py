#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,importlib.util,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4.2-MF2-IMPORTED-CERTIFIED-MONOTONIC-GAM-RESOLUTION-FORENSICS-1.0"
TARGET="CertifiedMonotonicGAM"

class ForensicsError(RuntimeError):pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

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

def seg(text,node):
    try:return ast.get_source_segment(text,node) or ""
    except Exception:return ""

def scan_imports(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    rows=[]
    target_bindings=[]
    for n in tree.body:
        if isinstance(n,ast.ImportFrom):
            module=n.module or ""
            for a in n.names:
                local=a.asname or a.name
                row={"kind":"ImportFrom","module":module,"imported":a.name,"local_name":local,"lineno":n.lineno,"source":seg(text,n)}
                rows.append(row)
                if local==TARGET or a.name==TARGET:
                    target_bindings.append(row)
        elif isinstance(n,ast.Import):
            for a in n.names:
                local=a.asname or a.name
                rows.append({"kind":"Import","module":a.name,"imported":"","local_name":local,"lineno":n.lineno,"source":seg(text,n)})
    return text,tree,rows,target_bindings

def module_candidates(root,module):
    rel=Path(*module.split("."))
    cands=[
        root/(str(rel)+".py"),
        root/"src"/(str(rel)+".py"),
        root/rel/"__init__.py",
        root/"src"/rel/"__init__.py",
    ]
    return [p.resolve() for p in cands if p.exists()]

def find_class_in_file(path,class_name):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name==class_name:
            body=seg(text,n)
            methods=[]
            for m in n.body:
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    methods.append({
                        "name":m.name,
                        "lineno":m.lineno,
                        "end_lineno":getattr(m,"end_lineno",m.lineno),
                        "source_sha256":hashlib.sha256(seg(text,m).encode()).hexdigest(),
                    })
            return {
                "class_name":class_name,
                "lineno":n.lineno,
                "end_lineno":getattr(n,"end_lineno",n.lineno),
                "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
                "methods":methods,
            }
    return None

# M77.19.8.7.10.7.2.4.2.1-ARGPARSE-NAMESPACE-BINDING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-call-graph-json",default="reports/m77_19_8_7_10_7_2_4_exact_mf2_solver_call_graph_extraction_development_parity_gate.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_2_mf2_imported_certified_monotonic_gam_resolution_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_2_mf2_import_resolution_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    failed=load_json(resolve(root,args.failed_call_graph_json))
    if failed.get("status")!="BLOCKED_EXACT_MF2_SOLVER_CALL_GRAPH_NOT_CERTIFIED":
        raise ForensicsError("expected blocked 10.7.2.4 report")
    if failed.get("MF2_all_horizons_explicit_config_parity") is not True:
        raise ForensicsError("MF2 frozen config parity not complete")
    if failed.get("validation_scoring_execution_authorized") is not False:
        raise ForensicsError("Validation scoring unexpectedly authorized")

    script=resolve(root,args.mf2_development_script)
    text,tree,imports,target_bindings=scan_imports(script)

    # Also detect module-qualified use such as foo.CertifiedMonotonicGAM.
    qualified_modules=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Attribute) and n.attr==TARGET and isinstance(n.value,ast.Name):
            qualified_modules.add(n.value.id)

    resolved=[]
    for b in target_bindings:
        for p in module_candidates(root,b["module"]):
            ce=find_class_in_file(p,b["imported"])
            resolved.append({
                "binding":b,
                "module_file":str(p),
                "module_file_sha256":sha256_file(p),
                "class_evidence":ce,
            })

    # If the direct import is re-exported from __init__, follow imports one level.
    second_level=[]
    for r in list(resolved):
        if r["class_evidence"] is None and Path(r["module_file"]).name=="__init__.py":
            init_text,init_tree,init_imports,init_targets=scan_imports(Path(r["module_file"]))
            for ib in init_targets:
                parent_module=r["binding"]["module"]
                mod=ib["module"]
                if mod.startswith("."):
                    mod=mod.lstrip(".")
                    full=parent_module+"."+mod if mod else parent_module
                else:
                    full=mod
                for p in module_candidates(root,full):
                    ce=find_class_in_file(p,ib["imported"])
                    second_level.append({
                        "binding":ib,
                        "module_file":str(p),
                        "module_file_sha256":sha256_file(p),
                        "class_evidence":ce,
                    })
    resolved.extend(second_level)

    certified=[r for r in resolved if r.get("class_evidence")]
    root_cause=None
    if certified:
        root_cause="CERTIFIED_MONOTONIC_GAM_IMPORTED_FROM_EXTERNAL_PROJECT_MODULE"
    elif target_bindings:
        root_cause="CERTIFIED_MONOTONIC_GAM_IMPORT_FOUND_BUT_CLASS_DEFINITION_NOT_RESOLVED"
    else:
        root_cause="CERTIFIED_MONOTONIC_GAM_DIRECT_IMPORT_BINDING_NOT_FOUND"

    status="READY" if certified else "BLOCKED_IMPORTED_CLASS_DEFINITION_NOT_RESOLVED"

    rows=[]
    for b in imports:
        rows.append({
            "record_type":"IMPORT",
            "module":b["module"],
            "imported":b["imported"],
            "local_name":b["local_name"],
            "lineno":b["lineno"],
            "module_file":"",
            "module_file_sha256":"",
            "class_found":"",
            "class_source_sha256":"",
        })
    for r in resolved:
        ce=r.get("class_evidence")
        rows.append({
            "record_type":"RESOLUTION",
            "module":r["binding"]["module"],
            "imported":r["binding"]["imported"],
            "local_name":r["binding"]["local_name"],
            "lineno":r["binding"]["lineno"],
            "module_file":r["module_file"],
            "module_file_sha256":r["module_file_sha256"],
            "class_found":bool(ce),
            "class_source_sha256":ce.get("source_sha256") if ce else "",
        })

    report={
        "version":VERSION,
        "status":status,
        "failed_call_graph_sha256":sha256_file(resolve(root,args.failed_call_graph_json)),
        "MF2_development_script_sha256":sha256_file(script),
        "target_symbol":TARGET,
        "direct_target_import_binding_count":len(target_bindings),
        "direct_target_import_bindings":target_bindings,
        "qualified_target_module_aliases":sorted(qualified_modules),
        "resolved_candidates":resolved,
        "certified_class_definition_count":len(certified),
        "root_cause_certified":bool(certified),
        "root_cause":root_cause,
        "imported_class_resolution_certified":bool(certified),
        "exact_imported_class_binding_authorized":bool(certified),
        "MF2_formula_reimplementation_authorized":False,
        "MF2_semantic_equivalent_rewrite_authorized":False,
        "validation_scoring_execution_authorized":False,
        "validation_scoring_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_4_3_EXACT_IMPORTED_CERTIFIED_MONOTONIC_GAM_BINDING_AND_FIT_CHAIN_PARITY_GATE"
            if certified else
            "REVIEW_M77_19_8_7_10_7_2_4_2_IMPORTED_CLASS_RESOLUTION_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["record_type","module","imported","local_name","lineno","module_file","module_file_sha256","class_found","class_source_sha256"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.4.2 MF2 IMPORTED CERTIFIED MONOTONIC GAM RESOLUTION FORENSICS ===")
    print("status:",status)
    print("MF2_development_script_sha256:",sha256_file(script))
    print("direct_target_import_binding_count:",len(target_bindings))
    for i,b in enumerate(target_bindings,1):
        print(f"import_binding_{i}: module={b['module']} imported={b['imported']} local={b['local_name']} line={b['lineno']}")
    print("qualified_target_module_aliases:",sorted(qualified_modules))
    print("resolved_candidate_count:",len(resolved))
    for i,r in enumerate(resolved,1):
        ce=r.get("class_evidence")
        print(f"resolved_{i}: file={r['module_file']} class_found={bool(ce)} class_sha256={ce.get('source_sha256') if ce else None}")
    print("certified_class_definition_count:",len(certified))
    print("root_cause_certified:",bool(certified))
    print("root_cause:",root_cause)
    print("imported_class_resolution_certified:",bool(certified))
    print("exact_imported_class_binding_authorized:",bool(certified))
    print("MF2_formula_reimplementation_authorized: False")
    print("MF2_semantic_equivalent_rewrite_authorized: False")
    print("validation_scoring_execution_authorized: False")
    print("validation_scoring_performed: False")
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
