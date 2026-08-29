#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile,time
from pathlib import Path
import numpy as np

VERSION="M77.19.8.7.5-MF2-EXECUTION-PREFLIGHT-MF3-SCALABLE-SOLVER-PARITY-AUTHORITY-1.0"
EXPECTED_874_VERSION="M77.19.8.7.4-MF2-RUNTIME-MF3-ELASTIC-NET-QUANTILE-SOLVER-CERTIFICATION-1.0"

class PreflightError(RuntimeError):pass
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def pinball(y,p,q):
    r=np.asarray(y)-np.asarray(p)
    return float(np.where(r>=0,q*r,(q-1)*r).mean())

def objective(y,p,beta,q,a,r):
    return pinball(y,p,q)+float(a*(r*np.abs(beta).sum()+(1-r)*0.5*np.dot(beta,beta)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--solver-certification-json",default="reports/m77_19_8_7_4_mf2_runtime_mf3_elastic_net_quantile_solver_certification.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_5_mf2_execution_preflight_mf3_scalable_solver_parity_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_5_solver_parity_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    cp=resolve(root,a.solver_certification_json);cert=load_json(cp)
    if cert.get("version")!=EXPECTED_874_VERSION or cert.get("status")!="READY":raise PreflightError("M77.19.8.7.4 authority invalid")
    if cert.get("validation_open_authorized") is not False or cert.get("final_holdout_open_authorized") is not False:raise PreflightError("sealed partitions violated")

    from trading_ai.research.m77.m77_19_8_7_4_certified_solvers import CertifiedElasticNetQuantile,CertifiedMonotonicGAM
    from trading_ai.research.m77.m77_19_8_7_5_scalable_solvers import PrimalDualElasticNetQuantile

    rng=np.random.default_rng(77)

    # MF2 execution preflight: deterministic scaling benchmark + monotonic contract on a larger synthetic matrix.
    n2=5000;p2=12
    X2=rng.normal(size=(n2,p2))
    eta=0.8*X2[:,0]-0.7*X2[:,1]+0.25*X2[:,2]
    y2=(rng.random(n2)<1/(1+np.exp(-eta))).astype(float)
    signs=[1,-1]+[0]*(p2-2)
    t=time.perf_counter()
    gam=CertifiedMonotonicGAM(knot_count=4,l2_penalty=0.1,max_iter=250).fit(X2,y2,signs)
    elapsed_mf2=time.perf_counter()-t
    grid=np.linspace(-2,2,80)
    a1=np.zeros((len(grid),p2));a1[:,0]=grid
    a2=np.zeros((len(grid),p2));a2[:,1]=grid
    mf2_ok=bool(np.all(np.diff(gam.predict_proba(a1)[:,1])>=-1e-9) and np.all(np.diff(gam.predict_proba(a2)[:,1])<=1e-9))
    if not mf2_ok:raise PreflightError("MF2 monotonic execution preflight failed")

    # MF3 parity against the exact 8.7.4 reference on moderate deterministic cases.
    parity=[]
    for seed in (7,17):
        rg=np.random.default_rng(seed)
        X=rg.normal(size=(120,4))
        y=0.5+0.9*X[:,0]-0.45*X[:,1]+rg.normal(scale=.35,size=len(X))
        for q in (.25,.5,.75):
            for alpha in (.001,.01):
                for l1r in (0.,.5,1.):
                    ref=CertifiedElasticNetQuantile(q,alpha,l1r,max_iter=700,tol=1e-8).fit(X,y)
                    fast=PrimalDualElasticNetQuantile(q,alpha,l1r,max_iter=12000,tol=2e-7).fit(X,y)
                    pref=ref.predict(X);pfast=fast.predict(X)
                    oref=objective(y,pref,ref.coef_,q,alpha,l1r)
                    ofast=objective(y,pfast,fast.coef_,q,alpha,l1r)
                    rel=(ofast-oref)/max(abs(oref),1e-9)
                    parity.append({
                        "seed":seed,"quantile":q,"alpha":alpha,"l1_ratio":l1r,
                        "reference_objective":oref,"scalable_objective":ofast,
                        "relative_objective_gap":rel,"scalable_iterations":fast.n_iter_,
                        "parity_pass":bool(rel<=0.015),
                    })
    mf3_ok=all(x["parity_pass"] for x in parity)
    max_gap=max(x["relative_objective_gap"] for x in parity)
    if not mf3_ok:raise PreflightError(f"MF3 scalable parity failed; max_relative_objective_gap={max_gap}")

    report={
      "version":VERSION,"status":"READY","solver_certification_sha256":sha256_file(cp),
      "MF2":{
        "execution_preflight_row_count":n2,"execution_preflight_feature_count":p2,
        "elapsed_seconds":elapsed_mf2,"monotonic_contract_passed":mf2_ok,
        "development_walk_forward_execution_authorized":True,
        "development_walk_forward_executed":False,
      },
      "MF3":{
        "scalable_runtime":"PRIMAL_DUAL_PINBALL_ELASTIC_NET",
        "parity_case_count":len(parity),"max_relative_objective_gap":max_gap,
        "parity_tolerance":0.015,"all_parity_cases_passed":mf3_ok,
        "scalable_solver_certified":True,
        "development_walk_forward_execution_authorized":True,
        "development_walk_forward_executed":False,
      },
      "validation_open_authorized":False,"final_holdout_open_authorized":False,
      "MF1_retuning_authorized":False,"production_authority_effect":False,
      "next_step":"BUILD_M77_19_8_7_6_DEVELOPMENT_ONLY_MF2_MF3_WALK_FORWARD_EVALUATION_WITH_CHECKPOINTS",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=list(parity[0].keys());w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(parity)
    print("=== M77.19.8.7.5 MF2 EXECUTION PREFLIGHT & MF3 SCALABLE SOLVER PARITY AUTHORITY ===")
    print("status: READY")
    print("MF2_execution_preflight_rows:",n2)
    print("MF2_elapsed_seconds:",elapsed_mf2)
    print("MF2_monotonic_contract_passed:",mf2_ok)
    print("MF2_development_walk_forward_execution_authorized: True")
    print("MF2_development_walk_forward_executed: False")
    print("MF3_parity_case_count:",len(parity))
    print("MF3_max_relative_objective_gap:",max_gap)
    print("MF3_all_parity_cases_passed:",mf3_ok)
    print("MF3_scalable_solver_certified: True")
    print("MF3_development_walk_forward_execution_authorized: True")
    print("MF3_development_walk_forward_executed: False")
    print("validation_open_authorized: False")
    print("final_holdout_open_authorized: False")
    print("MF1_retuning_authorized: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_6_DEVELOPMENT_ONLY_MF2_MF3_WALK_FORWARD_EVALUATION_WITH_CHECKPOINTS")
    print("report:",oj);print("csv:",oc)
    return 0
if __name__=="__main__":raise SystemExit(main())
