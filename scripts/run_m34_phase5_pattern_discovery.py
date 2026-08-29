import argparse, json
from pathlib import Path
from types import SimpleNamespace
from trading_ai.research_workstation.pattern_discovery import PatternDiscoveryEngine, write_pattern_discovery, write_similarity_report

def ns(v):
    if isinstance(v,dict): return SimpleNamespace(**{k:ns(x) for k,x in v.items()})
    if isinstance(v,list): return tuple(ns(x) for x in v)
    return v

def main():
    p=argparse.ArgumentParser(description="Run Milestone 34 Phase 5 Step 2 pattern discovery.")
    p.add_argument("--knowledge-base-json",default="reports/m34/phase5/research_knowledge_base.json")
    p.add_argument("--output-dir",default="reports/m34/phase5")
    a=p.parse_args(); source=Path(a.knowledge_base_json)
    if not source.exists(): raise FileNotFoundError(f"Knowledge base not found: {source}")
    kb=ns(json.loads(source.read_text(encoding="utf-8"))); out=Path(a.output_dir); engine=PatternDiscoveryEngine()
    sim=engine.build_similarity_report(knowledge_base=kb); pat=engine.build_pattern_discovery(knowledge_base=kb)
    sp=write_similarity_report(sim,out/"similar_research_cases.json"); pp=write_pattern_discovery(pat,out/"pattern_discovery.json")
    print("Milestone 34 Phase 5 Step 2 pattern discovery completed.")
    print(f"Similarity report: {sp}"); print(f"Pattern report: {pp}")
    print(f"Similarity status: {sim.governance_status}"); print(f"Pattern status: {pat.governance_status}")
    print(f"Matches: {sim.match_count}"); print(f"Clusters: {pat.cluster_count}")
if __name__=="__main__": main()
