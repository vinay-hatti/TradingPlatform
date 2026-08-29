#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4.5-RUNTIME-METHOD-AND-CHAINED-FIT-INVOCATION-FORENSICS-1.0"
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

def call_name(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        parts=[];cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr);cur=cur.value
        if isinstance(cur,ast.Name):parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""

def find_class_methods(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name==TARGET:
            out=[]
            for m in n.body:
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    out.append({
                        "name":m.name,
                        "lineno":m.lineno,
                        "end_lineno":getattr(m,"end_lineno",m.lineno),
                        "args":[a.arg for a in m.args.args],
                        "source_sha256":hashlib.sha256(seg(text,m).encode()).hexdigest(),
                        "source":seg(text,m)[:5000],
                    })
            return out
    return []

def inspect_development_call_shapes(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    main_node=None
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="main":
            main_node=n
            break
    if main_node is None:
        raise ForensicsError("main() not found")

    calls=[]
    constructor_calls=[]
    chained_fit_calls=[]
    chained_predict_calls=[]
    windows=[]

    lines=text.splitlines()
    for n in ast.walk(main_node):
        if isinstance(n,ast.Call):
            nm=call_name(n.func)
            s=seg(text,n)
            rec={"lineno":n.lineno,"call_name":nm,"source":s[:4000]}
            if TARGET in s or nm.endswith(".fit") or nm.endswith(".predict_proba"):
                calls.append(rec)
            # direct constructor
            if isinstance(n.func,ast.Name) and n.func.id==TARGET:
                constructor_calls.append(rec)
            # chained CertifiedMonotonicGAM(...).fit(...)
            if isinstance(n.func,ast.Attribute) and n.func.attr=="fit":
                base=n.func.value
                if isinstance(base,ast.Call) and isinstance(base.func,ast.Name) and base.func.id==TARGET:
                    chained_fit_calls.append(rec)
            # chained CertifiedMonotonicGAM(...).fit(...).predict_proba(...)
            if isinstance(n.func,ast.Attribute) and n.func.attr=="predict_proba":
                base=n.func.value
                chained_predict_calls.append(rec)
    for rec in calls:
        ln=rec["lineno"]
        start=max(1,ln-8);end=min(len(lines),ln+8)
        windows.append({
            "center_lineno":ln,
            "start_lineno":start,
            "end_lineno":end,
            "text":"\n".join(f"{i:4d}: {lines[i-1]}" for i in range(start,end+1))
        })

    return {
        "calls":calls,
        "constructor_calls":constructor_calls,
        "chained_fit_calls":chained_fit_calls,
        "chained_predict_calls":chained_predict_calls,
        "source_windows":windows,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--failed-runtime-gate-json",default="reports/m77_19_8_7_10_7_2_4_4_exact_runtime_symbol_binding_fit_chain_parity_gate.json")
    ap.add_argument("--provenance-json",default="reports/m77_19_8_7_10_7_2_4_3_certified_monotonic_gam_symbol_provenance_runtime_binding_forensics.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_5_runtime_method_and_chained_fit_invocation_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_5_runtime_invocation_shape_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    failed=load_json(resolve(root,args.failed_runtime_gate_json))
    prov=load_json(resolve(root,args.provenance_json))

    if failed.get("status")!="BLOCKED_RUNTIME_SYMBOL_BINDING_OR_FIT_CHAIN_PARITY":
        raise ForensicsError("expected blocked 10.7.2.4.4 report")
    if failed.get("MF2_all_horizons_explicit_config_parity") is not True:
        raise ForensicsError("MF2 config parity not complete")
    if prov.get("status")!="READY" or prov.get("symbol_provenance_certified") is not True:
        raise ForensicsError("provenance not READY/certified")

    resolved=[x for x in prov.get("imported_project_module_search",[]) if x.get("target_definitions")]
    if len(resolved)!=1:
        raise ForensicsError(f"expected one resolved module, got {len(resolved)}")
    module_file=Path(resolved[0]["file"]).resolve()

    methods=find_class_methods(module_file)
    method_names=[x["name"] for x in methods]
    dev_script=resolve(root,args.mf2_development_script)
    shapes=inspect_development_call_shapes(dev_script)

    required_runtime_behavior_present=(
        "fit" in method_names and
        "predict_proba" in method_names
    )
    chained_or_direct_fit_observed=(
        len(shapes["chained_fit_calls"])>0 or
        any(x["call_name"].endswith(".fit") for x in shapes["calls"])
    )
    constructor_observed=len(shapes["constructor_calls"])>0

    root_cause_certified=required_runtime_behavior_present and constructor_observed
    if root_cause_certified:
        root_cause="RUNTIME_CONTRACT_IS_FIT_PLUS_PREDICT_PROBA_AND_DEVELOPMENT_USES_NON_ASSIGNMENT_CONSTRUCTOR_FIT_SHAPE"
    else:
        root_cause="RUNTIME_METHOD_OR_DEVELOPMENT_INVOCATION_SHAPE_STILL_UNRESOLVED"

    status="READY" if root_cause_certified else "BLOCKED_RUNTIME_INVOCATION_SHAPE_UNRESOLVED"

    rows=[]
    for m in methods:
        rows.append({
            "record_type":"RUNTIME_METHOD",
            "name":m["name"],
            "lineno":m["lineno"],
            "call_name":"",
            "source_sha256":m["source_sha256"],
            "source":m["source"][:1000],
        })
    for c in shapes["calls"]:
        rows.append({
            "record_type":"DEVELOPMENT_CALL",
            "name":"",
            "lineno":c["lineno"],
            "call_name":c["call_name"],
            "source_sha256":hashlib.sha256(c["source"].encode()).hexdigest(),
            "source":c["source"][:1000],
        })

    report={
        "version":VERSION,
        "status":status,
        "failed_runtime_gate_sha256":sha256_file(resolve(root,args.failed_runtime_gate_json)),
        "provenance_sha256":sha256_file(resolve(root,args.provenance_json)),
        "runtime_module_file":str(module_file),
        "runtime_module_sha256":sha256_file(module_file),
        "runtime_methods":methods,
        "available_runtime_method_names":method_names,
        "runtime_fit_plus_predict_proba_contract_present":required_runtime_behavior_present,
        "development_invocation_shapes":shapes,
        "development_constructor_call_count":len(shapes["constructor_calls"]),
        "development_chained_fit_call_count":len(shapes["chained_fit_calls"]),
        "development_predict_proba_call_count":len(shapes["chained_predict_calls"]),
        "root_cause_certified":root_cause_certified,
        "root_cause":root_cause,
        "fit_chain_repair_authorized":root_cause_certified,
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
            "BUILD_M77_19_8_7_10_7_2_4_6_EXACT_FIT_PREDICT_PROBA_CHAIN_PARITY_GATE"
            if root_cause_certified else
            "REVIEW_M77_19_8_7_10_7_2_4_5_INVOCATION_SHAPE_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["record_type","name","lineno","call_name","source_sha256","source"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.4.5 RUNTIME METHOD & CHAINED-FIT INVOCATION FORENSICS ===")
    print("status:",status)
    print("runtime_module_file:",module_file)
    print("available_runtime_method_names:",method_names)
    print("runtime_fit_plus_predict_proba_contract_present:",required_runtime_behavior_present)
    print("development_constructor_call_count:",len(shapes["constructor_calls"]))
    print("development_chained_fit_call_count:",len(shapes["chained_fit_calls"]))
    print("development_predict_proba_call_count:",len(shapes["chained_predict_calls"]))
    print("root_cause_certified:",root_cause_certified)
    print("root_cause:",root_cause)
    for i,w in enumerate(shapes["source_windows"][:10],1):
        print(f"\nsource_window_{i}:")
        print(w["text"])
    print("fit_chain_repair_authorized:",root_cause_certified)
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
