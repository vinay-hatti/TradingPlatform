from __future__ import annotations
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from .dynamic_risk_limit_profile import RiskAlertProfile

class JsonRiskAlertRepository:
    def __init__(self,path: str|Path='data/position_monitoring/risk_alerts.json') -> None: self.path=Path(path)
    def _load(self):
        if not self.path.exists(): return {}
        payload=json.loads(self.path.read_text(encoding='utf-8')); return {k:RiskAlertProfile(**v) for k,v in payload.get('alerts',{}).items()}
    def _save(self,items):
        self.path.parent.mkdir(parents=True,exist_ok=True); temp=self.path.with_suffix(self.path.suffix+'.tmp'); temp.write_text(json.dumps({'alerts':{k:asdict(v) for k,v in items.items()}},indent=2,sort_keys=True)+'\n',encoding='utf-8'); temp.replace(self.path)
    def save_all(self,alerts):
        items=self._load()
        for a in alerts: items[a.alert_id]=a
        self._save(items); return tuple(alerts)
    def mark_sent(self,alert_id):
        items=self._load(); item=items[alert_id]; item=replace(item,status='SENT',attempt_count=item.attempt_count+1,sent_at=datetime.now(timezone.utc).isoformat()); items[alert_id]=item; self._save(items); return item
    def for_breach(self,breach_id): return tuple(v for v in self._load().values() if v.breach_id==breach_id)
