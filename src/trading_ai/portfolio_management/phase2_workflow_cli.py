from __future__ import annotations
import argparse,json
from pathlib import Path
from .phase2_workflow_service import Milestone36Phase2WorkflowService

def main()->int:
    p=argparse.ArgumentParser(description='Milestone 36 Phase 2 unified workflow')
    p.add_argument('command',choices=('run','discover'))
    p.add_argument('--candidates')
    p.add_argument('--candidate-root',default='reports/m35')
    p.add_argument('--registry-file',default='data/portfolio/m36_portfolio_registry.json')
    p.add_argument('--output-dir',default='reports/m36/phase2')
    a=p.parse_args(); s=Milestone36Phase2WorkflowService()
    if a.command=='discover': payload={'candidate_file':str(s.discover_candidate_file(Path(a.candidate_root)))}
    else: payload=s.run(Path(a.candidates) if a.candidates else None,Path(a.registry_file),Path(a.output_dir)).to_dict()
    print(json.dumps(payload,indent=2)); return 0
