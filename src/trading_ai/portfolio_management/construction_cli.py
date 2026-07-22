from __future__ import annotations
import argparse,json
from pathlib import Path
from .construction_profile import PortfolioConstructionPolicyProfile
from .construction_service import PortfolioConstructionOrchestrationService
from .phase2_workflow_service import Milestone36Phase2WorkflowService

def main()->int:
    parser=argparse.ArgumentParser(description='Milestone 36 Phase 2 portfolio construction')
    parser.add_argument('command',choices=('construct','normalize','discover'))
    parser.add_argument('--candidates')
    parser.add_argument('--candidate-root',default='reports/m35')
    parser.add_argument('--registry-file',default='data/portfolio/m36_portfolio_registry.json')
    parser.add_argument('--output-file',default='reports/m36/phase2/portfolio_construction.json')
    parser.add_argument('--portfolio-id',default='PRIMARY')
    args=parser.parse_args(); discovery=Milestone36Phase2WorkflowService()
    if args.command=='discover':
        print(json.dumps({'candidate_file':str(discovery.discover_candidate_file(Path(args.candidate_root)))},indent=2)); return 0
    candidate_path=Path(args.candidates) if args.candidates else discovery.discover_candidate_file(Path(args.candidate_root))
    if not candidate_path.exists(): raise SystemExit(f'Candidate artifact not found: {candidate_path}. Run the discover command or omit --candidates for auto-discovery.')
    service=PortfolioConstructionOrchestrationService(PortfolioConstructionPolicyProfile(portfolio_id=args.portfolio_id)); candidates=service.normalizer.load_file(candidate_path)
    if args.command=='normalize':
        payload={'candidate_file':str(candidate_path),'candidate_count':len(candidates),'candidates':[x.to_dict() for x in candidates]}; Path(args.output_file).parent.mkdir(parents=True,exist_ok=True); Path(args.output_file).write_text(json.dumps(payload,indent=2)+'\n')
    else: payload=service.construct(candidates,Path(args.registry_file),Path(args.output_file),str(candidate_path)).to_dict()
    print(json.dumps(payload,indent=2,default=str)); return 0
