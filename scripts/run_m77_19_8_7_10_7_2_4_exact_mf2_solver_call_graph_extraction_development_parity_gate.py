#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4-EXACT-MF2-SOLVER-CALL-GRAPH-EXTRACTION-DEVELOPMENT-PARITY-GATE-1.0"
MF2="MF2_MONOTONIC_GAM_DIRECTION"
HORIZONS=(5,10,20)
REQUIRED_CONFIGS={
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

def call_name(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):
        parts=[];cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr);cur=cur.value
        if isinstance(cur,ast.Name):parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""

def scan_exact_chain(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)

    defs={}
    classes={}
    main_node=None
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            defs[n.name]=n
            if n.name=="main": main_node=n
        elif isinstance(n,ast.ClassDef):
            classes[n.name]=n
    if main_node is None: raise GateError("MF2 script missing main")

    constructor_calls=[]
    fit_calls=[]
    for n in ast.walk(main_node):
        if isinstance(n,ast.Call):
            nm=call_name(n.func)
            src=seg(text,n)
            if nm.endswith("CertifiedMonotonicGAM"):
                constructor_calls.append({"lineno":n.lineno,"call":nm,"source":src})
            if nm.endswith(".fit") and "CertifiedMonotonicGAM" in text[max(0,text.find(src)-3000):text.find(src)+len(src)+3000]:
                fit_calls.append({"lineno":n.lineno,"call":nm,"source":src})
            elif nm=="fit" and "CertifiedMonotonicGAM" in src:
                fit_calls.append({"lineno":n.lineno,"call":nm,"source":src})

    # More reliable: assignment receiving CertifiedMonotonicGAM and subsequent .fit
    model_vars=set()
    assignment_evidence=[]
    for n in ast.walk(main_node):
        if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call):
            nm=call_name(n.value.func)
            if nm.endswith("CertifiedMonotonicGAM"):
                for t in n.targets:
                    if isinstance(t,ast.Name):
                        model_vars.add(t.id)
                        assignment_evidence.append({
                            "var":t.id,"lineno":n.lineno,
                            "source":seg(text,n),
                        })
    model_fit_calls=[]
    for n in ast.walk(main_node):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="fit":
            if isinstance(n.func.value,ast.Name) and n.func.value.id in model_vars:
                model_fit_calls.append({
                    "var":n.func.value.id,
                    "lineno":n.lineno,
                    "source":seg(text,n),
                })

    class_node=classes.get("CertifiedMonotonicGAM")
    class_ev=None
    if class_node:
        body=seg(text,class_node)
        methods=[]
        for n in class_node.body:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                methods.append({
                    "name":n.name,
                    "lineno":n.lineno,
                    "end_lineno":getattr(n,"end_lineno",n.lineno),
                    "source_sha256":hashlib.sha256(seg(text,n).encode()).hexdigest(),
                })
        class_ev={
            "name":"CertifiedMonotonicGAM",
            "lineno":class_node.lineno,
            "end_lineno":getattr(class_node,"end_lineno",class_node.lineno),
            "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
            "methods":methods,
        }

    helper_names=set()
    if class_node:
        class_body=seg(text,class_node)
        for name in defs:
            if name!="main" and name in class_body:
                helper_names.add(name)
    helpers=[]
    for name in sorted(helper_names):
        n=defs[name]
        body=seg(text,n)
        helpers.append({
            "name":name,
            "lineno":n.lineno,
            "end_lineno":getattr(n,"end_lineno",n.lineno),
            "source_sha256":hashlib.sha256(body.encode()).hexdigest(),
        })

    return {
        "script_sha256":sha256_file(path),
        "model_vars":sorted(model_vars),
        "constructor_assignment_evidence":assignment_evidence,
        "model_fit_calls":model_fit_calls,
        "class_evidence":class_ev,
        "supporting_helpers":helpers,
    }

def extract_configs(d):
    out={}
    def walk(x):
        if isinstance(x,dict):
            fam=x.get("family");h=x.get("horizon")
            cfg=x.get("selected_config") or x.get("config")
            if fam==MF2 and h in HORIZONS and isinstance(cfg,dict):
                out[str(h)]=cfg
            for key in ("selected_configs_by_horizon","frozen_MF2_selected_configs","selected_configs"):
                v=x.get(key)
                if isinstance(v,dict):
                    for hh in HORIZONS:
                        c=v.get(str(hh)) or v.get(hh)
                        if isinstance(c,dict):out[str(hh)]=c
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(d)
    return out

# M77.19.8.7.10.7.2.4.1-ARGPARSE-ATTRIBUTE-BINDING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_7_2_3_mf2_main_call_graph_solver_extraction_forensics.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--preregistration-json",default="reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_exact_mf2_solver_call_graph_extraction_development_parity_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_mf2_exact_call_graph_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    fx=load_json(resolve(root,args.forensics_json))
    pre=load_json(resolve(root,args.preregistration_json))
    dev=load_json(resolve(root,args.mf2_development_json))

    if fx.get("status")!="READY" or fx.get("root_cause_certified") is not True:
        raise GateError("10.7.2.3 forensics not READY/certified")
    if fx.get("root_cause")!="MF2_MODEL_LOGIC_IN_NESTED_MAIN_LOCAL_CALLABLES":
        raise GateError("unexpected 10.7.2.3 root-cause classification")
    if fx.get("validation_scoring_execution_authorized") is not False:
        raise GateError("Validation scoring unexpectedly authorized by forensics")
    if pre.get("status")!="READY":
        raise GateError("10.7 preregistration not READY")

    path=resolve(root,args.mf2_development_script)
    if sha256_file(path)!=fx.get("MF2_development_analysis",{}).get("script_sha256"):
        raise GateError("MF2 Development script SHA changed after forensics")

    chain=scan_exact_chain(path)
    class_ev=chain["class_evidence"]
    exact_chain_located=(
        class_ev is not None and
        len(chain["constructor_assignment_evidence"])>0 and
        len(chain["model_fit_calls"])>0
    )

    configs=extract_configs(dev)
    parity={}
    for h in HORIZONS:
        parity[str(h)]=(configs.get(str(h))==REQUIRED_CONFIGS[str(h)])
    explicit_config_parity=all(parity[str(h)] is True for h in HORIZONS)

    # `save_checkpoint` was a false-positive nested semantic tag. The certifiable
    # chain is the exact class + constructor assignment + model.fit call.
    false_positive_nested_save_checkpoint=any(
        x.get("name")=="save_checkpoint"
        for x in fx.get("MF2_development_analysis",{}).get("nested_solver_candidates",[])
    )

    exact_contract=exact_chain_located and explicit_config_parity

    registry=[]
    if class_ev:
        registry.append({
            "component_type":"CLASS",
            "name":class_ev["name"],
            "lineno":class_ev["lineno"],
            "end_lineno":class_ev["end_lineno"],
            "source_sha256":class_ev["source_sha256"],
        })
        for m in class_ev["methods"]:
            registry.append({
                "component_type":"CLASS_METHOD",
                "name":f"{class_ev['name']}.{m['name']}",
                "lineno":m["lineno"],
                "end_lineno":m["end_lineno"],
                "source_sha256":m["source_sha256"],
            })
    for h in chain["supporting_helpers"]:
        registry.append({
            "component_type":"SUPPORTING_HELPER",
            "name":h["name"],
            "lineno":h["lineno"],
            "end_lineno":h["end_lineno"],
            "source_sha256":h["source_sha256"],
        })

    status="READY" if exact_contract else "BLOCKED_EXACT_MF2_SOLVER_CALL_GRAPH_NOT_CERTIFIED"
    report={
        "version":VERSION,
        "status":status,
        "forensics_sha256":sha256_file(resolve(root,args.forensics_json)),
        "MF2_development_script_sha256":chain["script_sha256"],
        "MF2_exact_call_graph":chain,
        "MF2_nested_save_checkpoint_false_positive_identified":false_positive_nested_save_checkpoint,
        "MF2_certifiable_model_class":"CertifiedMonotonicGAM" if class_ev else None,
        "MF2_constructor_assignment_count":len(chain["constructor_assignment_evidence"]),
        "MF2_model_fit_call_count":len(chain["model_fit_calls"]),
        "MF2_frozen_config_parity":parity,
        "MF2_all_horizons_explicit_config_parity":explicit_config_parity,
        "MF2_exact_solver_call_graph_certified":exact_contract,
        "development_invocation_parity_certified":exact_contract,
        "development_model_refit_performed":False,
        "development_retuning_performed":False,
        "validation_scoring_execution_authorized":exact_contract,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_5_COMBINED_MF1_MF2_EXACT_INVOCATION_AUTHORITY"
            if exact_contract else
            "REVIEW_M77_19_8_7_10_7_2_4_EXACT_MF2_CALL_GRAPH_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["component_type","name","lineno","end_lineno","source_sha256"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in registry:w.writerow(r)

    print("=== M77.19.8.7.10.7.2.4 EXACT MF2 SOLVER CALL-GRAPH EXTRACTION & DEVELOPMENT PARITY GATE ===")
    print("status:",status)
    print("MF2_nested_save_checkpoint_false_positive_identified:",false_positive_nested_save_checkpoint)
    print("MF2_certifiable_model_class:",report["MF2_certifiable_model_class"])
    print("MF2_constructor_assignment_count:",report["MF2_constructor_assignment_count"])
    print("MF2_model_fit_call_count:",report["MF2_model_fit_call_count"])
    print("MF2_frozen_config_parity:",parity)
    print("MF2_all_horizons_explicit_config_parity:",explicit_config_parity)
    print("MF2_exact_solver_call_graph_certified:",exact_contract)
    print("development_invocation_parity_certified:",exact_contract)
    print("development_model_refit_performed: False")
    print("development_retuning_performed: False")
    print("validation_scoring_execution_authorized:",exact_contract)
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
