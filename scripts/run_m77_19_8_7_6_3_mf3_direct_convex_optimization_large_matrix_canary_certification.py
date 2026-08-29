#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,tempfile,time
from pathlib import Path
import numpy as np

VERSION="M77.19.8.7.6.3-MF3-DIRECT-CONVEX-OPTIMIZATION-LARGE-MATRIX-CANARY-CERTIFICATION-1.0"
EXPECTED_875_VERSION="M77.19.8.7.5-MF2-EXECUTION-PREFLIGHT-MF3-SCALABLE-SOLVER-PARITY-AUTHORITY-1.0"

class CertError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--execution-authority-json",default="reports/m77_19_8_7_5_mf2_execution_preflight_mf3_scalable_solver_parity_authority.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_6_3_mf3_direct_convex_optimization_large_matrix_canary_certification.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_6_3_mf3_direct_solver_certification_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    xp=resolve(root,a.execution_authority_json);ex=load_json(xp)
    if ex.get("version")!=EXPECTED_875_VERSION or ex.get("status")!="READY":raise CertError("M77.19.8.7.5 authority invalid")
    if ex.get("validation_open_authorized") is not False or ex.get("final_holdout_open_authorized") is not False:
        raise CertError("sealed partition governance violated")

    from trading_ai.research.m77.m77_19_8_7_4_certified_solvers import CertifiedElasticNetQuantile,pinball_loss_residual,elastic_net_penalty
    from trading_ai.research.m77.m77_19_8_7_6_3_direct_mf3 import DirectProximalSubgradientQuantile,exact_objective

    rows=[]
    max_gap=-1e9
    for seed in (7,17):
        rg=np.random.default_rng(seed)
        X=rg.normal(size=(120,4))
        y=.5+.9*X[:,0]-.45*X[:,1]+rg.normal(scale=.35,size=len(X))
        for q in (.25,.5,.75):
            for alpha in (.001,.01):
                for l1r in (0.,.5,1.):
                    ref=CertifiedElasticNetQuantile(q,alpha,l1r,max_iter=700,tol=1e-8).fit(X,y)
                    direct=DirectProximalSubgradientQuantile(q,alpha,l1r,max_iter=8000,tol=1e-7,initial_step=.35).fit(X,y)
                    ref_obj=exact_objective(X,y,ref.coef_,ref.intercept_,q,alpha,l1r)
                    gap=(direct.objective_-ref_obj)/max(abs(ref_obj),1e-9)
                    max_gap=max(max_gap,gap)
                    passed=bool(gap<=0.015)
                    rows.append({"stage":"REFERENCE_PARITY","seed":seed,"n":len(X),"p":X.shape[1],"quantile":q,"alpha":alpha,"l1_ratio":l1r,
                                 "reference_objective":ref_obj,"direct_objective":direct.objective_,"relative_objective_gap":gap,
                                 "elapsed_seconds":direct.elapsed_seconds_,"iterations":direct.n_iter_,"pass":passed})
                    if not passed:raise CertError(f"direct solver parity failed: seed={seed} q={q} alpha={alpha} l1={l1r} gap={gap}")

    # Scaling benchmark: no outcomes from Validation/Final Holdout; deterministic synthetic only.
    scaling=[]
    for n in (5000,20000):
        rg=np.random.default_rng(7700+n)
        X=rg.normal(size=(n,24))
        y=.4+.8*X[:,0]-.55*X[:,1]+.2*X[:,2]+rg.normal(scale=.45,size=n)
        t=time.perf_counter()
        m=DirectProximalSubgradientQuantile(.5,.001,.5,max_iter=600,tol=5e-6,initial_step=.3).fit(X,y)
        elapsed=time.perf_counter()-t
        scaling.append({"stage":"SYNTHETIC_SCALING","n":n,"p":24,"quantile":.5,"alpha":.001,"l1_ratio":.5,
                        "elapsed_seconds":elapsed,"iterations":m.n_iter_,"objective":m.objective_,"pass":bool(elapsed<120.0)})
        if elapsed>=120.0:raise CertError(f"synthetic scaling gate failed at n={n}: {elapsed}s")

    report={
        "version":VERSION,"status":"READY","execution_authority_sha256":sha256_file(xp),
        "solver_architecture":"DIRECT_PROXIMAL_SUBGRADIENT_EXACT_OBJECTIVE",
        "exact_mf3_objective_preserved":True,
        "parity_tolerance":0.015,
        "reference_parity_case_count":len(rows),
        "max_relative_objective_gap":max_gap,
        "all_reference_parity_cases_passed":True,
        "synthetic_scaling_benchmarks":scaling,
        "real_development_canary_authorized":True,
        "real_development_canary_executed":False,
        "full_development_walk_forward_authorized":False,
        "validation_open_authorized":False,
        "final_holdout_open_authorized":False,
        "production_authority_effect":False,
        "next_step":"RUN_SINGLE_REAL_WF1_H5_Q050_CANARY_BEFORE_FULL_MF3_DEVELOPMENT_REAUTHORIZATION",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=sorted({k for r in rows+scaling for k in r})
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows+scaling)
    print("=== M77.19.8.7.6.3 MF3 DIRECT CONVEX OPTIMIZATION & LARGE-MATRIX CANARY CERTIFICATION ===")
    print("status: READY")
    print("solver_architecture: DIRECT_PROXIMAL_SUBGRADIENT_EXACT_OBJECTIVE")
    print("reference_parity_case_count:",len(rows))
    print("max_relative_objective_gap:",max_gap)
    print("all_reference_parity_cases_passed: True")
    print("synthetic_scaling_benchmarks:",scaling)
    print("real_development_canary_authorized: True")
    print("real_development_canary_executed: False")
    print("full_development_walk_forward_authorized: False")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("production_authority_effect: False")
    print("next_step: RUN_SINGLE_REAL_WF1_H5_Q050_CANARY_BEFORE_FULL_MF3_DEVELOPMENT_REAUTHORIZATION")
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
