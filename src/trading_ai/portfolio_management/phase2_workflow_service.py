from __future__ import annotations
import json
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from .construction_service import PortfolioConstructionOrchestrationService
from .allocation_service import PortfolioAwareCapitalAllocationService
from .constraint_service import PortfolioConstraintValidationService
from .scenario_service import PortfolioConstructionScenarioService
from .handoff_service import PortfolioExecutionHandoffService
from .serialization import read_json,write_json_atomic

@dataclass(frozen=True)
class Phase2WorkflowResult:
    status:str
    candidate_file:str
    construction_file:str
    allocation_file:str
    constraints_file:str
    scenarios_file:str
    handoff_file:str
    report_file:str
    recommended_scenario:str
    proposed_position_count:int
    order_count:int
    generated_at:str
    def to_dict(self):return asdict(self)

class Milestone36Phase2WorkflowService:
    def discover_candidate_file(self, root:Path=Path('reports/m35')) -> Path:
        patterns=('*rank*.json','*opportunit*.json','*candidate*.json')
        found=[]
        for pattern in patterns: found.extend(root.rglob(pattern) if root.exists() else [])
        found=[p for p in found if p.is_file() and 'normalized' not in p.name.lower()]
        if not found: raise FileNotFoundError(f'No ranked opportunity artifact found under {root}')
        def quality(p:Path):
            score=0
            s=str(p).lower()
            if 'opportunity_rank' in s: score+=50
            if 'dashboard' in s: score+=20
            if 'phase5' in s: score+=10
            try:
                payload=json.loads(p.read_text())
                rows=payload.get('ranked_opportunities',payload.get('candidates',payload.get('opportunities',[]))) if isinstance(payload,dict) else payload
                if isinstance(rows,list): score+=min(len(rows),20)
            except Exception: score-=100
            return (score,p.stat().st_mtime)
        return max(found,key=quality)
    def run(self,candidate_file:Path|None,registry_file:Path,output_dir:Path) -> Phase2WorkflowResult:
        candidate_file=candidate_file or self.discover_candidate_file()
        output_dir.mkdir(parents=True,exist_ok=True)
        registry=read_json(registry_file)
        construction_file=output_dir/'portfolio_construction.json'
        construction=PortfolioConstructionOrchestrationService().construct_file(candidate_file,registry_file,construction_file)
        allocation=PortfolioAwareCapitalAllocationService().allocate(list(construction.proposed_positions),registry)
        allocation_file=output_dir/'capital_allocation.json'; write_json_atomic(allocation_file,allocation.to_dict())
        constraints=PortfolioConstraintValidationService().validate(list(allocation.allocations),registry)
        constraints_file=output_dir/'constraint_validation.json'; write_json_atomic(constraints_file,constraints.to_dict())
        scenarios=PortfolioConstructionScenarioService().compare(list(construction.proposed_positions),registry)
        scenarios_file=output_dir/'scenario_comparison.json'; write_json_atomic(scenarios_file,scenarios.to_dict())
        handoff_file=output_dir/'execution_handoff.json'
        handoff=PortfolioExecutionHandoffService().create(list(allocation.allocations),constraints.to_dict(),construction.portfolio_id,handoff_file)
        report={'milestone':'36','phase':'2','status':'COMPLETE' if constraints.valid else 'REVIEW_REQUIRED','candidate_file':str(candidate_file),'construction':construction.to_dict(),'allocation':allocation.to_dict(),'constraints':constraints.to_dict(),'scenarios':scenarios.to_dict(),'handoff':handoff.to_dict(),'generated_at':datetime.now(timezone.utc).isoformat()}
        report_file=output_dir/'phase2_closure.json'; write_json_atomic(report_file,report)
        html=output_dir/'phase2_closure.html'; html.write_text(self._html(report),encoding='utf-8')
        result=Phase2WorkflowResult(report['status'],str(candidate_file),str(construction_file),str(allocation_file),str(constraints_file),str(scenarios_file),str(handoff_file),str(report_file),scenarios.recommended_scenario,construction.proposed_position_count,handoff.order_count,report['generated_at'])
        write_json_atomic(output_dir/'workflow_result.json',result.to_dict()); return result
    @staticmethod
    def _html(r:dict[str,Any])->str:
        c=r['construction']; a=r['allocation']; x=r['constraints']; h=r['handoff']
        return f'''<!doctype html><html><head><meta charset="utf-8"><title>Milestone 36 Phase 2</title><style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:8px}}.ok{{color:green}}.bad{{color:#a00}}</style></head><body><h1>Milestone 36 Phase 2 Closure</h1><h2 class="{'ok' if r['status']=='COMPLETE' else 'bad'}">{r['status']}</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Candidates</td><td>{c['candidate_count']}</td></tr><tr><td>Proposed positions</td><td>{c['proposed_position_count']}</td></tr><tr><td>Allocated capital</td><td>{a['allocated_capital']}</td></tr><tr><td>Constraint violations</td><td>{len(x['violations'])}</td></tr><tr><td>Orders</td><td>{h['order_count']}</td></tr></table></body></html>'''
