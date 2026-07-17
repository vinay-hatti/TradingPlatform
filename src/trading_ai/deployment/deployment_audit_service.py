from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import json

@dataclass(frozen=True)
class DeploymentAuditEvent:
    deployment_id: str
    event_type: str
    environment: str
    release_version: str
    operator: str
    status: str
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DeploymentAuditService:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self._events = []

    def record(self, event):
        self._events.append(event)
        self._persist()

    def events(self, deployment_id=None):
        return tuple(self._events if deployment_id is None else [x for x in self._events if x.deployment_id == deployment_id])

    def _persist(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(
            json.dumps({'events': [asdict(x) for x in self._events]}, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        tmp.replace(self.path)
