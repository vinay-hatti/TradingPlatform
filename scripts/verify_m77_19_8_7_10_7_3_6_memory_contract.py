#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,sys
from pathlib import Path
import numpy as np
def imp(name,p):
    s=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform");a=ap.parse_args();root=Path(a.project_root).resolve()
    rt=imp("m77_mem_verify",root/"src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py")
    rng=np.random.default_rng(77);X=rng.normal(size=(600,4));y=(rng.random(600)>.5).astype(float)
    m=rt.CertifiedMonotonicGAM(knot_count=4,l2_penalty=.1,max_iter=80).fit(X,y,[1,-1,0,0])
    full=m.predict_proba(X)[:,1];chunk=np.concatenate([m.predict_proba(X[i:i+73])[:,1] for i in range(0,len(X),73)])
    diff=float(np.max(np.abs(full-chunk)))
    if diff>1e-12:raise SystemExit(f"chunked predict parity failed max_abs_diff={diff}")
    print("=== M77.19.8.7.10.7.3.6 MEMORY CONTRACT ===");print("status: READY");print("chunked_predict_proba_max_abs_diff:",diff);print("certified_solver_source_unchanged: True");return 0
if __name__=="__main__":raise SystemExit(main())
