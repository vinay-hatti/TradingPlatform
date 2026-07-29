from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .operations_engine import TrendOperationsEngine
from .operations_policy import TrendOperationsPolicy
from .operations_serialization import append_history, read_json, write_json_atomic

class TrendOperationsService:
    def __init__(self, root: Path|str='.', policy: TrendOperationsPolicy|None=None):
        self.root=Path(root); self.policy=policy or TrendOperationsPolicy(); self.engine=TrendOperationsEngine(self.root,self.policy)
        self.out=self.root/'reports/trend_intelligence'
    def run(self) -> dict[str,Any]:
        d=self.engine.load(); hist=read_json(self.out/'drift_history.json',[])
        assessments=[self.engine.health(d),self.engine.calibration(d),self.engine.drift(d,hist if isinstance(hist,list) else []),self.engine.attribution(d),self.engine.governance(d)]
        by={a.name:a.to_dict() for a in assessments}
        blocking=[f for a in assessments for f in a.findings if f.blocking]
        degraded=[a.name for a in assessments if a.status not in ('READY','NOT_ENOUGH_HISTORY')]
        status='FAILED' if blocking else ('DEGRADED' if degraded else 'READY')
        score=sum(a.score for a in assessments)/len(assessments)
        payload={'schema_version':self.policy.schema_version,'status':status,'score':round(score,4),'snapshot_timestamp':datetime.now(timezone.utc).isoformat(),'assessments':by,'blocking_findings':[asdict(f) for f in blocking],'degraded_components':degraded,'milestone_52_closure_eligible':status=='READY' and not blocking}
        for name,val in by.items(): write_json_atomic(self.out/f'{name}_latest.json',val)
        append_history(self.out/'drift_history.json',by['drift'])
        append_history(self.out/'operations_history.json',payload)
        write_json_atomic(self.out/'phase6_latest.json',payload)
        self._html(payload)
        return payload
    def _html(self,p):
        rows=''.join(f"<tr><td>{k}</td><td>{v['status']}</td><td>{v['score']:.1f}</td></tr>" for k,v in p['assessments'].items())
        html=("<!doctype html><html><head><meta charset='utf-8'><title>Milestone 52 Scorecard</title>"
              "<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:10px;text-align:left}}h1{{margin-bottom:4px}}</style>"
              f"</head><body><h1>Milestone 52 Trend Intelligence</h1><p>Phase 6 operational scorecard</p><h2>Status: {p['status']} — {p['score']:.1f}</h2><table><tr><th>Assessment</th><th>Status</th><th>Score</th></tr>{rows}</table><p>Closure eligible: {p['milestone_52_closure_eligible']}</p></body></html>")
        path=self.out/'executive_summary_latest.html'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(html)
