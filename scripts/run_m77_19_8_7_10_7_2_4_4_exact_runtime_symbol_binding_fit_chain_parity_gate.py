#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4.4-EXACT-RUNTIME-SYMBOL-BINDING-FIT-CHAIN-PARITY-GATE-1.0"
TARGET="CertifiedMonotonicGAM"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=(5,10,20)
FROZEN={
    "5":{"l2_penalty":0.1,"spline_knots":4},
    "10":{"l2_penalty":0.1,"spline_knots":4},
    "20":{"l2_penalty":0.1,"spline_knots":4},
}

class GateError(RuntimeError): pass

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

def find_class(path,name):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name==name:
            methods={}
            for m in n.body:
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    body=seg(text,m)
                    methods[m.name]={
                        "lineno":m.lineno,
                        "end_lineno":getattr(m,"end_lineno",m.lineno),
                        "args":[a.arg for a in m.args.args],
                        "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
                    }
            body=seg(text,n)
            return {
                "lineno":n.lineno,
                "end_lineno":getattr(n,"end_lineno",n.lineno),
                "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
                "methods":methods,
            }
    return None

def find_import_and_fit_chain(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)

    import_rows=[]
    main_node=None
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="main":
            main_node=n
    if main_node is None:
        raise GateError("MF2 Development script missing main")

    for n in ast.walk(main_node):
        if isinstance(n,ast.ImportFrom):
            for a in n.names:
                local=a.asname or a.name
                if a.name==TARGET or local==TARGET:
                    import_rows.append({
                        "module":n.module or "",
                        "imported":a.name,
                        "local_name":local,
                        "lineno":n.lineno,
                        "source":seg(text,n),
                    })

    model_vars={}
    constructor_rows=[]
    for n in ast.walk(main_node):
        if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call):
            func=n.value.func
            func_name=func.id if isinstance(func,ast.Name) else ""
            if func_name==TARGET:
                for t in n.targets:
                    if isinstance(t,ast.Name):
                        model_vars[t.id]=n.lineno
                        constructor_rows.append({
                            "var":t.id,
                            "lineno":n.lineno,
                            "source":seg(text,n),
                        })

    fit_rows=[]
    predict_rows=[]
    for n in ast.walk(main_node):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name):
            var=n.func.value.id
            if var in model_vars:
                if n.func.attr=="fit":
                    fit_rows.append({"var":var,"lineno":n.lineno,"source":seg(text,n)})
                if n.func.attr.startswith("predict"):
                    predict_rows.append({"var":var,"lineno":n.lineno,"method":n.func.attr,"source":seg(text,n)})

    return {
        "imports":import_rows,
        "constructors":constructor_rows,
        "fits":fit_rows,
        "predicts":predict_rows,
        "model_vars":sorted(model_vars),
    }

def extract_configs(d):
    out={}
    def walk(x):
        if isinstance(x,dict):
            fam=x.get("family"); h=x.get("horizon")
            cfg=x.get("selected_config") or x.get("config")
            if fam==MF2 and h in HORIZONS and isinstance(cfg,dict):
                out[str(h)]=cfg
            for key in ("selected_configs_by_horizon","frozen_MF2_selected_configs","selected_configs"):
                v=x.get(key)
                if isinstance(v,dict):
                    for hh in HORIZONS:
                        cc=v.get(str(hh)) or v.get(hh)
                        if isinstance(cc,dict): out[str(hh)]=cc
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(d)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--provenance-json",default="reports/m77_19_8_7_10_7_2_4_3_certified_monotonic_gam_symbol_provenance_runtime_binding_forensics.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_4_exact_runtime_symbol_binding_fit_chain_parity_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_4_runtime_fit_chain_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    prov=load_json(resolve(root,args.provenance_json))
    dev=load_json(resolve(root,args.mf2_development_json))

    if prov.get("status")!="READY" or prov.get("symbol_provenance_certified") is not True:
        raise GateError("10.7.2.4.3 provenance not READY/certified")
    if prov.get("validation_scoring_execution_authorized") is not False:
        raise GateError("Validation scoring unexpectedly authorized upstream")

    resolved=prov.get("imported_project_module_search") or []
    candidates=[]
    for r in resolved:
        defs=r.get("target_definitions") or []
        if defs:
            candidates.append(r)
    if len(candidates)!=1:
        raise GateError(f"expected exactly one resolved project module definition, found {len(candidates)}")

    module_file=Path(candidates[0]["file"]).resolve()
    if not module_file.exists():
        raise GateError("resolved CertifiedMonotonicGAM module file missing")
    if sha256_file(module_file)!=candidates[0]["file_sha256"]:
        raise GateError("resolved CertifiedMonotonicGAM module SHA changed")

    class_ev=find_class(module_file,TARGET)
    if not class_ev:
        raise GateError("CertifiedMonotonicGAM class not found in resolved module")
    required_methods={"__init__","fit","predict_score"}
    available=set(class_ev["methods"])
    method_contract_pass=required_methods.issubset(available)

    dev_script=resolve(root,args.mf2_development_script)
    if sha256_file(dev_script)!=prov.get("MF2_development_script_sha256"):
        raise GateError("MF2 Development script SHA changed after provenance certification")

    chain=find_import_and_fit_chain(dev_script)
    import_contract=(
        len(chain["imports"])==1 and
        chain["imports"][0]["module"]=="trading_ai.research.m77.m77_19_8_7_4_certified_solvers" and
        chain["imports"][0]["imported"]==TARGET and
        chain["imports"][0]["local_name"]==TARGET
    )
    fit_contract=(len(chain["constructors"])>=1 and len(chain["fits"])>=1)

    configs=extract_configs(dev)
    parity={str(h):(configs.get(str(h))==FROZEN[str(h)]) for h in HORIZONS}
    config_parity=all(parity[str(h)] is True for h in HORIZONS)

    certified=method_contract_pass and import_contract and fit_contract and config_parity
    status="READY" if certified else "BLOCKED_RUNTIME_SYMBOL_BINDING_OR_FIT_CHAIN_PARITY"

    rows=[]
    rows.append({
        "component":"RUNTIME_CLASS",
        "name":TARGET,
        "source":str(module_file),
        "lineno":class_ev["lineno"],
        "source_sha256":class_ev["source_sha256"],
        "certified":method_contract_pass,
    })
    for m,ev in sorted(class_ev["methods"].items()):
        rows.append({
            "component":"RUNTIME_METHOD",
            "name":f"{TARGET}.{m}",
            "source":str(module_file),
            "lineno":ev["lineno"],
            "source_sha256":ev["source_sha256"],
            "certified":m in required_methods,
        })
    for x in chain["imports"]:
        rows.append({
            "component":"DEVELOPMENT_IMPORT",
            "name":TARGET,
            "source":str(dev_script),
            "lineno":x["lineno"],
            "source_sha256":hashlib.sha256(x["source"].encode()).hexdigest(),
            "certified":import_contract,
        })
    for x in chain["constructors"]:
        rows.append({
            "component":"DEVELOPMENT_CONSTRUCTOR",
            "name":x["var"],
            "source":str(dev_script),
            "lineno":x["lineno"],
            "source_sha256":hashlib.sha256(x["source"].encode()).hexdigest(),
            "certified":True,
        })
    for x in chain["fits"]:
        rows.append({
            "component":"DEVELOPMENT_FIT",
            "name":x["var"]+".fit",
            "source":str(dev_script),
            "lineno":x["lineno"],
            "source_sha256":hashlib.sha256(x["source"].encode()).hexdigest(),
            "certified":True,
        })

    report={
        "version":VERSION,
        "status":status,
        "provenance_sha256":sha256_file(resolve(root,args.provenance_json)),
        "MF2_development_script_sha256":sha256_file(dev_script),
        "runtime_module_file":str(module_file),
        "runtime_module_sha256":sha256_file(module_file),
        "CertifiedMonotonicGAM_class_source_sha256":class_ev["source_sha256"],
        "CertifiedMonotonicGAM_methods":class_ev["methods"],
        "required_runtime_methods":sorted(required_methods),
        "runtime_method_contract_passed":method_contract_pass,
        "development_import_binding":chain["imports"],
        "development_constructor_bindings":chain["constructors"],
        "development_fit_bindings":chain["fits"],
        "development_predict_bindings":chain["predicts"],
        "exact_import_binding_certified":import_contract,
        "exact_constructor_fit_chain_certified":fit_contract,
        "MF2_frozen_config_parity":parity,
        "MF2_all_horizons_explicit_config_parity":config_parity,
        "exact_runtime_symbol_binding_and_fit_chain_certified":certified,
        "development_invocation_parity_certified":certified,
        "development_model_refit_performed":False,
        "development_retuning_performed":False,
        "validation_scoring_execution_authorized":certified,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_5_COMBINED_MF1_MF2_EXACT_INVOCATION_AUTHORITY"
            if certified else
            "REVIEW_M77_19_8_7_10_7_2_4_4_RUNTIME_BINDING_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["component","name","source","lineno","source_sha256","certified"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.4.4 EXACT RUNTIME SYMBOL BINDING & FIT-CHAIN PARITY GATE ===")
    print("status:",status)
    print("runtime_module_file:",module_file)
    print("runtime_module_sha256:",sha256_file(module_file))
    print("CertifiedMonotonicGAM_class_source_sha256:",class_ev["source_sha256"])
    print("available_runtime_methods:",sorted(available))
    print("required_runtime_methods:",sorted(required_methods))
    print("runtime_method_contract_passed:",method_contract_pass)
    print("development_import_binding_count:",len(chain["imports"]))
    print("development_constructor_binding_count:",len(chain["constructors"]))
    print("development_fit_binding_count:",len(chain["fits"]))
    print("exact_import_binding_certified:",import_contract)
    print("exact_constructor_fit_chain_certified:",fit_contract)
    print("MF2_frozen_config_parity:",parity)
    print("MF2_all_horizons_explicit_config_parity:",config_parity)
    print("exact_runtime_symbol_binding_and_fit_chain_certified:",certified)
    print("development_invocation_parity_certified:",certified)
    print("development_model_refit_performed: False")
    print("development_retuning_performed: False")
    print("validation_scoring_execution_authorized:",certified)
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
