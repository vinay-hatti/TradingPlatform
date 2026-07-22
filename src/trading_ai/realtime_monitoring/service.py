from __future__ import annotations
import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .event_bus import EventBus
from .models import AlertRecord, OperationalSnapshot, RealtimeEvent
from .policy import DEFAULT_RULES, matches

class RealtimeMonitoringService:
    def __init__(self, artifact_root: Path, poll_seconds: float = 2.0):
        self.artifact_root=artifact_root; self.poll_seconds=poll_seconds; self.bus=EventBus(); self.alerts: dict[str,AlertRecord]={}; self._mtimes={}; self._task=None
        self.artifacts={"risk":artifact_root/'m37/execution_risk_control.json',"execution":artifact_root/'m38/execution_queue.json',"positions":artifact_root/'m39/position_assessments.json',"exits":artifact_root/'m39/exit_instructions.json'}

    async def start(self):
        if self._task is None: self._task=asyncio.create_task(self._monitor())
    async def stop(self):
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
            self._task=None

    def _read(self,path):
        try: return json.loads(path.read_text())
        except Exception: return {}

    def _summary(self,name,payload,path):
        if name=='risk': return {'trading_control':payload.get('trading_control'),'allow_new_risk':payload.get('allow_new_risk'),'stale':False}
        rows=payload.get('orders') or payload.get('items') or payload.get('assessments') or payload.get('instructions') or (payload if isinstance(payload,list) else [])
        if not isinstance(rows,list): rows=[]
        if name=='execution': return {'total_orders':len(rows),'blocked_orders':sum(1 for x in rows if 'BLOCK' in str(x.get('status','')))}
        if name=='positions': return {'position_count':len(rows),'review_count':sum(1 for x in rows if x.get('decision')=='REVIEW')}
        return {'instruction_count':len(rows),'urgent_count':sum(1 for x in rows if x.get('urgency') in ('HIGH','CRITICAL'))}

    async def scan_once(self):
        for name,path in self.artifacts.items():
            if not path.exists(): continue
            mtime=path.stat().st_mtime
            if self._mtimes.get(name)==mtime: continue
            self._mtimes[name]=mtime; payload=self._read(path); summary=self._summary(name,payload,path)
            await self.bus.publish(RealtimeEvent(event_id=uuid4().hex,event_type='ARTIFACT_UPDATED',source=name,payload={'path':str(path),**summary}))
            for rule in DEFAULT_RULES:
                if rule.source==name and matches(rule,summary):
                    alert_id=f'{rule.rule_id}:{name}'
                    if alert_id not in self.alerts or self.alerts[alert_id].status=='RESOLVED':
                        alert=AlertRecord(alert_id=alert_id,rule_id=rule.rule_id,severity=rule.severity,title=rule.title,message=f'{rule.title}: {summary}',source=name)
                        self.alerts[alert_id]=alert
                        await self.bus.publish(RealtimeEvent(event_id=uuid4().hex,event_type='ALERT_OPENED',severity=rule.severity,source=name,payload=alert.model_dump(mode='json')))
        self._persist()

    async def _monitor(self):
        while True:
            await self.scan_once(); await asyncio.sleep(self.poll_seconds)

    def acknowledge(self,alert_id,actor):
        a=self.alerts[alert_id]; a.status='ACKNOWLEDGED'; a.acknowledged_by=actor; a.acknowledged_at=datetime.now(timezone.utc); self._persist(); return a
    def resolve(self,alert_id): self.alerts[alert_id].status='RESOLVED'; self._persist(); return self.alerts[alert_id]
    def _persist(self):
        out=self.artifact_root/'m42'; out.mkdir(parents=True,exist_ok=True)
        (out/'alerts.json').write_text(json.dumps({'alerts':[a.model_dump(mode='json') for a in self.alerts.values()]},indent=2))
        (out/'event_history.json').write_text(json.dumps({'events':[e.model_dump(mode='json') for e in self.bus.history(1000)]},indent=2))
        (out/'operational_snapshot.json').write_text(self.snapshot().model_dump_json(indent=2))
    def snapshot(self):
        watched={}
        now=datetime.now(timezone.utc).timestamp()
        for n,p in self.artifacts.items(): watched[n]={'path':str(p),'exists':p.exists(),'age_seconds':round(now-p.stat().st_mtime,2) if p.exists() else None}
        active=[a for a in self.alerts.values() if a.status!='RESOLVED']
        return OperationalSnapshot(service_status='UP',connected_clients=self.bus.connected_clients,events_published=self.bus.published,open_alerts=len(active),critical_alerts=sum(1 for a in active if a.severity=='CRITICAL'),watched_artifacts=watched)
