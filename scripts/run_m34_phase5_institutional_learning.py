from __future__ import annotations
import argparse,json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from trading_ai.research_workstation.institutional_learning import InstitutionalLearningEngine,write_institutional_learning,write_learning_summary

def ns(v:Any):
    if isinstance(v,dict): return SimpleNamespace(**{k:ns(x) for k,x in v.items()})
    if isinstance(v,list): return tuple(ns(x) for x in v)
    return v

def main():
    p=argparse.ArgumentParser(); p.add_argument("--knowledge-base-json",default="reports/m34/phase5/research_knowledge_base.json"); p.add_argument("--output-dir",default="reports/m34/phase5"); a=p.parse_args()
    src=Path(a.knowledge_base_json)
    if not src.exists(): raise FileNotFoundError(f"Knowledge base not found: {src}")
    profile=InstitutionalLearningEngine().build(knowledge_base=ns(json.loads(src.read_text(encoding="utf-8"))))
    out=Path(a.output_dir); f1=write_institutional_learning(profile,out/"institutional_learning.json"); f2=write_learning_summary(profile,out/"learning_summary.json")
    print("Milestone 34 Phase 5 Step 3 institutional learning completed."); print(f"Learning report: {f1}"); print(f"Summary report: {f2}"); print(f"Governance status: {profile.governance_status}"); print(f"Cases learned: {profile.summary.total_cases}"); print(f"Calibration error: {profile.summary.calibration_error:.6f}")
if __name__=="__main__": main()
