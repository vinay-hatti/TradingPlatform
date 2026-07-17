from __future__ import annotations
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from .dynamic_risk_limit_profile import RiskBreachProfile

class JsonRiskBreachRepository:
    def __init__(self,path: str|Path='data/position_monitoring/risk_breaches.json') -> None: self.path=Path(path)
    def _load(self):
        if not self.path.exists(): return {}
        payload=json.loads(self.path.read_text(encoding='utf-8'))
        return {k:RiskBreachProfile(**v) for k,v in payload.get('breaches',{}).items()}
    def _save(self,items):
        self.path.parent.mkdir(parents=True,exist_ok=True); temp=self.path.with_suffix(self.path.suffix+'.tmp')
        temp.write_text(json.dumps({'breaches':{k:asdict(v) for k,v in items.items()}},indent=2,sort_keys=True)+'\n',encoding='utf-8'); temp.replace(self.path)
    def get(self,breach_id): return self._load().get(breach_id)
    def save_or_increment(self,breach: RiskBreachProfile):
        items=self._load(); existing=items.get(breach.breach_id)
        if existing and existing.status!='RESOLVED':
            breach=replace(existing,observed_value=breach.observed_value,limit_value=breach.limit_value,severity=breach.severity,snapshot_id=breach.snapshot_id,occurrence_count=existing.occurrence_count+1,last_detected_at=breach.last_detected_at,metadata={**existing.metadata,**breach.metadata})
        items[breach.breach_id]=breach; self._save(items); return breach
    def acknowledge(self,breach_id,actor):
        items=self._load(); item=items[breach_id]; now=datetime.now(timezone.utc).isoformat(); item=replace(item,status='ACKNOWLEDGED',acknowledged_at=now,acknowledged_by=actor); items[breach_id]=item; self._save(items); return item
    def resolve(self,breach_id,note):
        items=self._load(); item=items[breach_id]; now=datetime.now(timezone.utc).isoformat(); item=replace(item,status='RESOLVED',resolved_at=now,resolution_note=note); items[breach_id]=item; self._save(items); return item
    def open_for_account(self,account_id): return tuple(v for v in self._load().values() if v.account_id==account_id and v.status!='RESOLVED')
