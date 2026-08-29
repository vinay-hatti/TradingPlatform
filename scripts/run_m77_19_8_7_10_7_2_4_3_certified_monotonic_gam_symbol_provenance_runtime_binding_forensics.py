#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4.3-CERTIFIED-MONOTONIC-GAM-SYMBOL-PROVENANCE-RUNTIME-BINDING-FORENSICS-1.0"
TARGET="CertifiedMonotonicGAM"

class ForensicsError(RuntimeError): pass

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

def name_of(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        parts=[];cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr);cur=cur.value
        if isinstance(cur,ast.Name):parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""

def module_paths(root,module):
    rel=Path(*module.split("."))
    cands=[
        root/(str(rel)+".py"),
        root/"src"/(str(rel)+".py"),
        root/rel/"__init__.py",
        root/"src"/rel/"__init__.py",
        root/"scripts"/(rel.name+".py"),
    ]
    return [p.resolve() for p in cands if p.exists()]

def find_symbol_defs(path,symbol):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    out=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.ClassDef) and n.name==symbol:
            out.append({
                "kind":"CLASS_DEF","name":symbol,"lineno":n.lineno,
                "end_lineno":getattr(n,"end_lineno",n.lineno),
                "source_sha256":hashlib.sha256(seg(text,n).encode()).hexdigest(),
            })
        elif isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=[]
            if isinstance(n,ast.Assign): targets=n.targets
            else: targets=[n.target]
            for t in targets:
                if isinstance(t,ast.Name) and t.id==symbol:
                    out.append({
                        "kind":"ASSIGNMENT","name":symbol,"lineno":n.lineno,
                        "end_lineno":getattr(n,"end_lineno",n.lineno),
                        "source":seg(text,n)[:2000],
                        "source_sha256":hashlib.sha256(seg(text,n).encode()).hexdigest(),
                    })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-import-forensics-json",default="reports/m77_19_8_7_10_7_2_4_2_mf2_imported_certified_monotonic_gam_resolution_forensics.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_3_certified_monotonic_gam_symbol_provenance_runtime_binding_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_3_symbol_provenance_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    failed=load_json(resolve(root,args.failed_import_forensics_json))
    if failed.get("status")!="BLOCKED_IMPORTED_CLASS_DEFINITION_NOT_RESOLVED":
        raise ForensicsError("expected blocked 10.7.2.4.2 report")
    if failed.get("validation_scoring_execution_authorized") is not False:
        raise ForensicsError("Validation scoring unexpectedly authorized")

    script=resolve(root,args.mf2_development_script)
    text=script.read_text(encoding="utf-8")
    tree=ast.parse(text)

    evidence=[]

    # Imports anywhere in module, including imports local to main()/helpers.
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            module=n.module or ""
            for a in n.names:
                local=a.asname or a.name
                if a.name=="*" or a.name==TARGET or local==TARGET:
                    evidence.append({
                        "kind":"IMPORT_FROM","lineno":n.lineno,
                        "module":module,"imported":a.name,"local_name":local,
                        "source":seg(text,n)[:2000],
                    })
        elif isinstance(n,ast.Import):
            for a in n.names:
                local=a.asname or a.name
                evidence.append({
                    "kind":"IMPORT_MODULE","lineno":n.lineno,
                    "module":a.name,"imported":"","local_name":local,
                    "source":seg(text,n)[:2000],
                })

    # Every Name load/store and Attribute use of TARGET.
    for n in ast.walk(tree):
        if isinstance(n,ast.Name) and n.id==TARGET:
            evidence.append({
                "kind":"NAME_"+type(n.ctx).__name__.upper(),
                "lineno":n.lineno,"module":"","imported":"","local_name":TARGET,
                "source":seg(text,n)[:2000],
            })
        elif isinstance(n,ast.Attribute) and n.attr==TARGET:
            evidence.append({
                "kind":"QUALIFIED_ATTRIBUTE","lineno":n.lineno,
                "module":name_of(n.value),"imported":TARGET,"local_name":"",
                "source":seg(text,n)[:2000],
            })

    # Assignments/aliases that can produce TARGET.
    alias_evidence=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            value=n.value
            for t in targets:
                if isinstance(t,ast.Name) and t.id==TARGET:
                    alias_evidence.append({
                        "kind":"TARGET_ASSIGNMENT","lineno":n.lineno,
                        "rhs":seg(text,value)[:2000],
                        "source":seg(text,n)[:3000],
                    })
                elif isinstance(value,ast.Name) and value.id==TARGET and isinstance(t,ast.Name):
                    alias_evidence.append({
                        "kind":"ALIAS_FROM_TARGET","lineno":n.lineno,
                        "alias":t.id,"rhs":TARGET,"source":seg(text,n)[:3000],
                    })
                elif isinstance(value,ast.Attribute) and value.attr==TARGET and isinstance(t,ast.Name):
                    alias_evidence.append({
                        "kind":"ALIAS_FROM_QUALIFIED_TARGET","lineno":n.lineno,
                        "alias":t.id,"rhs":name_of(value),"source":seg(text,n)[:3000],
                    })

    # Dynamic import/getattr patterns.
    dynamic=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Call):
            nm=name_of(n.func)
            s=seg(text,n)
            if nm in {"getattr","importlib.import_module","__import__"} or TARGET in s:
                if TARGET in s or nm in {"importlib.import_module","__import__"}:
                    dynamic.append({
                        "lineno":n.lineno,"call_name":nm,"source":s[:3000],
                    })

    # Search imported project modules for target definitions/re-exports.
    searched=[]
    imported_modules=sorted({
        e["module"] for e in evidence
        if e["kind"] in {"IMPORT_FROM","IMPORT_MODULE"} and e.get("module")
    })
    for mod in imported_modules:
        for p in module_paths(root,mod):
            defs=find_symbol_defs(p,TARGET)
            searched.append({
                "module":mod,
                "file":str(p),
                "file_sha256":sha256_file(p),
                "target_definitions":defs,
            })

    resolved=[x for x in searched if x["target_definitions"]]
    direct_local_defs=find_symbol_defs(script,TARGET)

    if direct_local_defs:
        root_cause="CERTIFIED_MONOTONIC_GAM_BOUND_BY_LOCAL_ASSIGNMENT_OR_CLASS"
    elif resolved:
        root_cause="CERTIFIED_MONOTONIC_GAM_RESOLVED_THROUGH_IMPORTED_PROJECT_MODULE"
    elif any(e["kind"]=="IMPORT_FROM" and e["imported"]=="*" for e in evidence):
        root_cause="CERTIFIED_MONOTONIC_GAM_POSSIBLY_INTRODUCED_BY_WILDCARD_IMPORT"
    elif dynamic:
        root_cause="CERTIFIED_MONOTONIC_GAM_POSSIBLY_BOUND_DRYNAMICALLY"
    else:
        root_cause="CERTIFIED_MONOTONIC_GAM_SYMBOL_PROVENANCE_UNRESOLVED"

    certified=bool(direct_local_defs or resolved)
    status="READY" if certified else "BLOCKED_SYMBOL_PROVENANCE_NOT_YET_CERTIFIED"

    rows=[]
    for e in evidence:
        rows.append({
            "record_type":e["kind"],"lineno":e["lineno"],
            "module":e.get("module",""),"symbol":e.get("imported") or e.get("local_name",""),
            "file":"","file_sha256":"","definition_kind":"","definition_sha256":"",
            "source":e.get("source","")[:1000],
        })
    for s in searched:
        for d in s["target_definitions"] or [{}]:
            rows.append({
                "record_type":"MODULE_SEARCH","lineno":d.get("lineno",""),
                "module":s["module"],"symbol":TARGET,
                "file":s["file"],"file_sha256":s["file_sha256"],
                "definition_kind":d.get("kind",""),
                "definition_sha256":d.get("source_sha256",""),
                "source":d.get("source","")[:1000],
            })

    report={
        "version":VERSION,
        "status":status,
        "failed_import_forensics_sha256":sha256_file(resolve(root,args.failed_import_forensics_json)),
        "MF2_development_script_sha256":sha256_file(script),
        "target_symbol":TARGET,
        "all_symbol_evidence":evidence,
        "alias_evidence":alias_evidence,
        "dynamic_binding_evidence":dynamic,
        "imported_project_module_search":searched,
        "local_target_definitions":direct_local_defs,
        "resolved_project_module_definition_count":len(resolved),
        "root_cause_certified":certified,
        "root_cause":root_cause,
        "symbol_provenance_certified":certified,
        "exact_runtime_binding_execution_authorized":certified,
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
            "BUILD_M77_19_8_7_10_7_2_4_4_EXACT_RUNTIME_SYMBOL_BINDING_AND_FIT_CHAIN_PARITY_GATE"
            if certified else
            "REVIEW_M77_19_8_7_10_7_2_4_3_SYMBOL_PROVENANCE_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["record_type","lineno","module","symbol","file","file_sha256","definition_kind","definition_sha256","source"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.4.3 CERTIFIED MONOTONIC GAM SYMBOL PROVENANCE & RUNTIME BINDING FORENSICS ===")
    print("status:",status)
    print("MF2_development_script_sha256:",sha256_file(script))
    print("target_symbol:",TARGET)
    print("symbol_evidence_count:",len(evidence))
    print("alias_evidence_count:",len(alias_evidence))
    print("dynamic_binding_evidence_count:",len(dynamic))
    print("imported_project_module_search_count:",len(searched))
    print("local_target_definition_count:",len(direct_local_defs))
    print("resolved_project_module_definition_count:",len(resolved))
    print("root_cause_certified:",certified)
    print("root_cause:",root_cause)
    for i,e in enumerate(evidence[:30],1):
        print(f"evidence_{i}: kind={e['kind']} line={e['lineno']} module={e.get('module')} imported={e.get('imported')} local={e.get('local_name')}")
    for i,s in enumerate(resolved[:10],1):
        print(f"resolved_module_{i}: module={s['module']} file={s['file']} sha256={s['file_sha256']} definitions={len(s['target_definitions'])}")
    print("symbol_provenance_certified:",certified)
    print("exact_runtime_binding_execution_authorized:",certified)
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
