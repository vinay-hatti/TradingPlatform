from __future__ import annotations
import argparse,json
from pathlib import Path
from types import SimpleNamespace
from trading_ai.research_workstation.outcome_attribution import OutcomeAttributionEngine,write_outcome_attribution_report,write_thesis_validation_report
def ns(v):
    if isinstance(v,dict): return SimpleNamespace(**{k:ns(x) for k,x in v.items()})
    if isinstance(v,list): return tuple(ns(x) for x in v)
    return v
def main():
    p=argparse.ArgumentParser(); p.add_argument("--research-case-json",required=True); p.add_argument("--scenario-comparison-json",required=True); p.add_argument("--decision-journal-json",required=True); p.add_argument("--realized-outcome-json",required=True); p.add_argument("--output",default="reports/m34/phase4/outcome_attribution.json"); p.add_argument("--thesis-output",default="reports/m34/phase4/thesis_validation.json"); p.add_argument("--attribution-id",default="ATTRIBUTION-001"); a=p.parse_args()
    paths=[Path(a.research_case_json),Path(a.scenario_comparison_json),Path(a.decision_journal_json),Path(a.realized_outcome_json)]
    for x in paths:
        if not x.exists(): raise FileNotFoundError(f"Input file not found: {x}")
    rc,sc,dj=map(lambda x:ns(json.loads(x.read_text())),paths[:3]); ro=json.loads(paths[3].read_text())
    r=OutcomeAttributionEngine().evaluate(attribution_id=a.attribution_id,research_case=rc,scenario_comparison=sc,decision_journal=dj,realized_outcome=ro)
    o=write_outcome_attribution_report(r,a.output); t=write_thesis_validation_report(r,a.thesis_output)
    print("Milestone 34 Phase 4 outcome attribution completed."); print(f"Outcome report: {o}"); print(f"Thesis report: {t}"); print(f"Outcome status: {r.outcome_status}"); print(f"Thesis validation: {r.thesis_validation['validation_status']}"); print(f"Decision quality: {r.decision_quality_score:.3f} ({r.decision_quality_grade})")
if __name__=="__main__": main()
