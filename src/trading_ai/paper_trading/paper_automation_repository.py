from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from .paper_automation_profile import PaperAutomationCheckpoint
class JsonPaperAutomationRepository:
    def __init__(self,path='data/paper_trading/automation_checkpoints.json'): self.path=Path(path)
    def _load(self):
        if not self.path.exists(): return {}
        raw=json.loads(self.path.read_text())
        return {k:PaperAutomationCheckpoint(**v) for k,v in raw.get('checkpoints',{}).items()}
    def _save(self,data):
        self.path.parent.mkdir(parents=True,exist_ok=True); t=self.path.with_suffix(self.path.suffix+'.tmp')
        t.write_text(json.dumps({'checkpoints':{k:asdict(v) for k,v in data.items()}},indent=2,sort_keys=True)+'\n'); t.replace(self.path)
    def get(self,key): return self._load().get(key)
    def save(self,c):
        d=self._load();d[c.checkpoint_id]=c;self._save(d);return c
    def all(self): return tuple(self._load().values())
