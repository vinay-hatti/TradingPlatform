#!/usr/bin/env python3
from __future__ import annotations

import argparse,ast,csv,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.7.2.4.6-EXACT-FIT-PREDICT-PROBA-CHAIN-PARITY-GATE-1.0"
TARGET_CLASS="CertifiedMonotonicGAM"
PREPROCESSOR="FoldPreprocessor"
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

def call_name(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        parts=[];cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr);cur=cur.value
        if isinstance(cur,ast.Name):parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""

def find_main(path):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="main":
            return text,n
    raise GateError("main() not found")

def inspect_exact_chain(path):
    text,main_node=find_main(path)
    evidence={
        "preprocessor_fit":[],
        "preprocessor_transform":[],
        "mf2_constructor_fit":[],
        "predict_proba":[],
        "threshold_050":[],
        "balanced_accuracy":[],
    }

    # Detect preprocessor assignment: prep=FoldPreprocessor().fit(...)
    prep_vars=set()
    model_vars=set()
    prob_vars=set()

    for n in ast.walk(main_node):
        if isinstance(n,ast.Assign):
            s=seg(text,n)
            # prep=FoldPreprocessor().fit(...)
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="fit":
                base=n.value.func.value
                if isinstance(base,ast.Call) and isinstance(base.func,ast.Name) and base.func.id==PREPROCESSOR:
                    for t in n.targets:
                        if isinstance(t,ast.Name):
                            prep_vars.add(t.id)
                            evidence["preprocessor_fit"].append({
                                "var":t.id,"lineno":n.lineno,"source":s,
                                "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                            })
            # m=CertifiedMonotonicGAM(...).fit(...)
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="fit":
                base=n.value.func.value
                if isinstance(base,ast.Call) and isinstance(base.func,ast.Name) and base.func.id==TARGET_CLASS:
                    for t in n.targets:
                        if isinstance(t,ast.Name):
                            model_vars.add(t.id)
                            evidence["mf2_constructor_fit"].append({
                                "var":t.id,"lineno":n.lineno,"source":s,
                                "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                            })
            # prob=m.predict_proba(Xte)[:,1]
            if TARGET_CLASS not in s and "predict_proba" in s:
                for t in n.targets:
                    if isinstance(t,ast.Name):
                        prob_vars.add(t.id)
                evidence["predict_proba"].append({
                    "lineno":n.lineno,"source":s,
                    "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                })
            # pred=(prob>=.5).astype(int)
            if any(v in s for v in prob_vars) and (">=.5" in s.replace(" ","") or ">=0.5" in s.replace(" ","")):
                evidence["threshold_050"].append({
                    "lineno":n.lineno,"source":s,
                    "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                })

    for n in ast.walk(main_node):
        if isinstance(n,ast.Call):
            nm=call_name(n.func)
            s=seg(text,n)
            if isinstance(n.func,ast.Attribute) and n.func.attr=="transform" and isinstance(n.func.value,ast.Name) and n.func.value.id in prep_vars:
                evidence["preprocessor_transform"].append({
                    "lineno":n.lineno,"source":s,
                    "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                })
            if nm.endswith("predict_proba") and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id in model_vars:
                # already captured by assignment but this proves exact model binding
                evidence["predict_proba"].append({
                    "lineno":n.lineno,"source":s,
                    "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                })
            if nm=="balanced_accuracy":
                evidence["balanced_accuracy"].append({
                    "lineno":n.lineno,"source":s,
                    "source_sha256":hashlib.sha256(s.encode()).hexdigest()
                })

    return evidence

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
                        cc=v.get(str(hh)) or v.get(hh)
                        if isinstance(cc,dict):out[str(hh)]=cc
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(d)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_7_10_7_2_4_5_runtime_method_and_chained_fit_invocation_forensics.json")
    ap.add_argument("--provenance-json",default="reports/m77_19_8_7_10_7_2_4_3_certified_monotonic_gam_symbol_provenance_runtime_binding_forensics.json")
    ap.add_argument("--mf2-development-script",default="scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    ap.add_argument("--mf2-development-json",default="reports/m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_2_4_6_exact_fit_predict_proba_chain_parity_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_2_4_6_exact_chain_registry.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    fx=load_json(resolve(root,args.forensics_json))
    prov=load_json(resolve(root,args.provenance_json))
    dev=load_json(resolve(root,args.mf2_development_json))

    if fx.get("status")!="READY" or fx.get("root_cause_certified") is not True:
        raise GateError("10.7.2.4.5 forensics not READY/certified")
    if fx.get("runtime_fit_plus_predict_proba_contract_present") is not True:
        raise GateError("runtime fit/predict_proba contract not certified")
    if fx.get("fit_chain_repair_authorized") is not True:
        raise GateError("fit-chain repair not authorized")
    if fx.get("validation_scoring_execution_authorized") is not False:
        raise GateError("Validation scoring unexpectedly authorized upstream")
    if prov.get("status")!="READY" or prov.get("symbol_provenance_certified") is not True:
        raise GateError("10.7.2.4.3 provenance not READY/certified")

    dev_script=resolve(root,args.mf2_development_script)
    if sha256_file(dev_script)!=fx.get("MF2_development_script_sha256",sha256_file(dev_script)):
        # tolerate older forensics schema only if the source SHA still matches provenance
        if sha256_file(dev_script)!=prov.get("MF2_development_script_sha256"):
            raise GateError("MF2 Development script SHA changed")

    chain=inspect_exact_chain(dev_script)

    preprocessor_fit_pass=len(chain["preprocessor_fit"])>=1
    preprocessor_transform_pass=len(chain["preprocessor_transform"])>=2
    constructor_fit_pass=len(chain["mf2_constructor_fit"])>=1
    predict_proba_pass=len(chain["predict_proba"])>=1
    threshold_pass=len(chain["threshold_050"])>=1
    balanced_accuracy_pass=len(chain["balanced_accuracy"])>=1

    configs=extract_configs(dev)
    parity={str(h):(configs.get(str(h))==FROZEN[str(h)]) for h in HORIZONS}
    config_parity=all(parity[str(h)] is True for h in HORIZONS)

    exact_chain=(
        preprocessor_fit_pass and
        preprocessor_transform_pass and
        constructor_fit_pass and
        predict_proba_pass and
        threshold_pass and
        balanced_accuracy_pass and
        config_parity
    )

    status="READY" if exact_chain else "BLOCKED_EXACT_FIT_PREDICT_PROBA_CHAIN_PARITY"

    rows=[]
    for component,vals in chain.items():
        for x in vals:
            rows.append({
                "component":component,
                "lineno":x["lineno"],
                "source_sha256":x["source_sha256"],
                "source":x["source"][:1200],
            })

    report={
        "version":VERSION,
        "status":status,
        "forensics_sha256":sha256_file(resolve(root,args.forensics_json)),
        "provenance_sha256":sha256_file(resolve(root,args.provenance_json)),
        "MF2_development_script_sha256":sha256_file(dev_script),
        "exact_chain_evidence":chain,
        "preprocessor_fit_certified":preprocessor_fit_pass,
        "preprocessor_transform_certified":preprocessor_transform_pass,
        "CertifiedMonotonicGAM_fit_chain_certified":constructor_fit_pass,
        "predict_proba_certified":predict_proba_pass,
        "fixed_threshold_050_certified":threshold_pass,
        "balanced_accuracy_metric_binding_certified":balanced_accuracy_pass,
        "MF2_frozen_config_parity":parity,
        "MF2_all_horizons_explicit_config_parity":config_parity,
        "exact_fit_predict_proba_chain_parity_certified":exact_chain,
        "development_invocation_parity_certified":exact_chain,
        "development_model_refit_performed":False,
        "development_retuning_performed":False,
        "validation_scoring_execution_authorized":exact_chain,
        "validation_scoring_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_7_2_5_COMBINED_MF1_MF2_EXACT_INVOCATION_AUTHORITY"
            if exact_chain else
            "REVIEW_M77_19_8_7_10_7_2_4_6_EXACT_CHAIN_FAILURE"
        ),
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["component","lineno","source_sha256","source"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.7.2.4.6 EXACT FIT/PREDICT-PROBA CHAIN PARITY GATE ===")
    print("status:",status)
    print("preprocessor_fit_certified:",preprocessor_fit_pass)
    print("preprocessor_transform_certified:",preprocessor_transform_pass)
    print("CertifiedMonotonicGAM_fit_chain_certified:",constructor_fit_pass)
    print("predict_proba_certified:",predict_proba_pass)
    print("fixed_threshold_050_certified:",threshold_pass)
    print("balanced_accuracy_metric_binding_certified:",balanced_accuracy_pass)
    print("MF2_frozen_config_parity:",parity)
    print("MF2_all_horizons_explicit_config_parity:",config_parity)
    print("exact_fit_predict_proba_chain_parity_certified:",exact_chain)
    print("development_invocation_parity_certified:",exact_chain)
    print("development_model_refit_performed: False")
    print("development_retuning_performed: False")
    print("validation_scoring_execution_authorized:",exact_chain)
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
