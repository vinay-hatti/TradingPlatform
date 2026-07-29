from __future__ import annotations
from typing import Any

def render_console(payload: dict[str,Any]) -> str:
    lines=['='*55,'Milestone 52 Phase 6 Operational Validation','='*55]
    for name,a in payload.get('assessments',{}).items(): lines.append(f"{name.replace('_',' ').title():28} {a.get('status','UNKNOWN'):18} {a.get('score',0):6.1f}")
    lines += ['-'*55,f"Overall Status: {payload.get('status')}",f"Overall Score : {payload.get('score')}",f"Closure Eligible: {payload.get('milestone_52_closure_eligible')}"]
    return '\n'.join(lines)
