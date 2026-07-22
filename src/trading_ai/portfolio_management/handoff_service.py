from __future__ import annotations
import hashlib
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from .serialization import write_json_atomic

@dataclass(frozen=True)
class ExecutionHandoffResult:
    handoff_id:str
    status:str
    portfolio_id:str
    order_count:int
    orders:tuple[dict[str,Any],...]
    generated_at:str
    def to_dict(self):return asdict(self)

class PortfolioExecutionHandoffService:
    def create(self, allocations:list[dict[str,Any]], constraints:dict[str,Any], portfolio_id='PRIMARY', output_file:Path|None=None):
        valid=bool(constraints.get('valid'))
        orders=[]
        if valid:
            for i,p in enumerate(allocations,1):
                orders.append({'client_order_id':f'M36-{portfolio_id}-{i:04d}','symbol':p.get('symbol'),'strategy':p.get('strategy'),'direction':p.get('direction'),'contracts':int(p.get('contracts',1)),'capital_limit':float(p.get('recommended_allocation',p.get('capital_required',0))),'status':'PENDING_PRETRADE_RISK','source_candidate_id':p.get('candidate_id','')})
        stamp=datetime.now(timezone.utc).isoformat(); digest=hashlib.sha256((portfolio_id+stamp).encode()).hexdigest()[:16].upper()
        result=ExecutionHandoffResult(f'M36-HANDOFF-{digest}','READY_FOR_PRETRADE_RISK' if orders else 'BLOCKED',portfolio_id,len(orders),tuple(orders),stamp)
        if output_file: write_json_atomic(output_file,result.to_dict())
        return result
