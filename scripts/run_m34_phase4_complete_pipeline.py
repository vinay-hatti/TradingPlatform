from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

def run(cmd:list[str])->None:
    print('+',' '.join(cmd)); subprocess.run(cmd,check=True)

def main()->None:
    ap=argparse.ArgumentParser(description='Run complete Milestone 34 Phase 4 workflow.')
    ap.add_argument('--case-id',default='CASE-001'); ap.add_argument('--symbol',default='AAPL'); ap.add_argument('--strategy',default='BULL_PUT_SPREAD')
    ap.add_argument('--output-dir',default='reports/m34/phase4')
    ap.add_argument('--journal-input-json',default='examples/m34_phase4_decision_journal_input.json')
    ap.add_argument('--realized-outcome-json',default='examples/m34_phase4_realized_outcome.json')
    a=ap.parse_args(); py=sys.executable; out=Path(a.output_dir)
    run([py,'scripts/run_m34_phase4_pipeline.py','--case-id',a.case_id,'--symbol',a.symbol,'--strategy',a.strategy,'--output-dir',str(out)])
    run([py,'scripts/run_m34_phase4_decision_journal.py','--research-case-json',str(out/'research_case.json'),'--scenario-comparison-json',str(out/'scenario_comparison.json'),'--journal-input-json',a.journal_input_json,'--output',str(out/'decision_journal.json')])
    run([py,'scripts/run_m34_phase4_outcome_attribution.py','--research-case-json',str(out/'research_case.json'),'--scenario-comparison-json',str(out/'scenario_comparison.json'),'--decision-journal-json',str(out/'decision_journal.json'),'--realized-outcome-json',a.realized_outcome_json,'--output',str(out/'outcome_attribution.json'),'--thesis-output',str(out/'thesis_validation.json')])
    run([py,'scripts/run_m34_phase4_dashboard.py','--phase4-dir',str(out),'--output-dir',str(out/'dashboard')])
    print('Milestone 34 Phase 4 complete pipeline finished successfully.')
if __name__=='__main__': main()
