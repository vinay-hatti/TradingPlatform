from __future__ import annotations
import argparse,json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from trading_ai.research_workstation.dashboard import (
    ResearchDashboardEngine, write_dashboard_summary,
    write_research_dashboard_html, write_research_dashboard_json,
)

def ns(v: Any)->Any:
    if isinstance(v,dict): return SimpleNamespace(**{k:ns(x) for k,x in v.items()})
    if isinstance(v,list): return tuple(ns(x) for x in v)
    return v

def load(path: Path)->Any:
    if not path.exists(): raise FileNotFoundError(f'Required Phase 4 report not found: {path}')
    return ns(json.loads(path.read_text(encoding='utf-8')))

def main()->None:
    ap=argparse.ArgumentParser(description='Generate Milestone 34 Phase 4 institutional dashboard.')
    ap.add_argument('--phase4-dir',default='reports/m34/phase4')
    ap.add_argument('--output-dir',default='reports/m34/phase4/dashboard')
    ap.add_argument('--dashboard-id',default='M34-P4-DASHBOARD-001')
    a=ap.parse_args(); src=Path(a.phase4_dir); out=Path(a.output_dir)
    paths={k:src/f for k,f in {'research_case':'research_case.json','scenario_comparison':'scenario_comparison.json','decision_journal':'decision_journal.json','outcome_attribution':'outcome_attribution.json','thesis_validation':'thesis_validation.json'}.items()}
    data={k:load(v) for k,v in paths.items()}
    result=ResearchDashboardEngine().build(dashboard_id=a.dashboard_id,source_artifacts={k:str(v) for k,v in paths.items()},**data)
    j=write_research_dashboard_json(result,out/'research_dashboard.json')
    h=write_research_dashboard_html(result,out/'research_dashboard.html')
    s=write_dashboard_summary(result,out/'research_dashboard_summary.json')
    phase=out/'phase4_summary.json'; phase.write_text(json.dumps({'milestone':34,'phase':4,'status':result.phase_completion.phase_status,'institutional_ready':result.scorecard.institutional_ready,'overall_score':result.scorecard.overall_score,'overall_grade':result.scorecard.overall_grade},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Milestone 34 Phase 4 dashboard completed.')
    print(f'Dashboard JSON: {j}'); print(f'Dashboard HTML: {h}'); print(f'Summary JSON: {s}')
    print(f'Phase status: {result.phase_completion.phase_status}')
    print(f'Institutional score: {result.scorecard.overall_score:.3f} ({result.scorecard.overall_grade})')

if __name__=='__main__': main()
