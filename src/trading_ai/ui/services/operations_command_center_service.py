from __future__ import annotations
import json,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
from trading_ai.ui.models.operations_command_center import *

class OperationsCommandCenterService:
    def __init__(self,state_path='reports/ui/operations_command_center_state.json',audit_path='reports/audit/operations_command_events.jsonl'):
        self.state_path=Path(state_path);self.audit_path=Path(audit_path);self._lock=RLock()
    @staticmethod
    def _now(): return datetime.now(timezone.utc)
    def _default(self): return {'runtime_controls':[],'incidents':[],'alerts':[],'releases':[],'locks':[],'service_overrides':{}}
    def _load(self):
        if not self.state_path.exists(): return self._default()
        d=self._default();d.update(json.loads(self.state_path.read_text()));return d
    def _save(self,s):
        self.state_path.parent.mkdir(parents=True,exist_ok=True);t=self.state_path.with_suffix('.tmp');t.write_text(json.dumps(s,indent=2));t.replace(self.state_path)
    def _audit(self,event,actor,obj,objid,before,after):
        self.audit_path.parent.mkdir(parents=True,exist_ok=True)
        row={'timestamp':self._now().isoformat(),'event_type':event,'actor_user_id':actor.user_id,'session_id':actor.session_id,'roles':actor.roles,'permissions':actor.permissions,'object_type':obj,'object_id':objid,'before':before,'after':after}
        with self.audit_path.open('a') as f:
            f.write(json.dumps(row) + '\n')
    def health_topology(self):
        s=self._load();now=self._now();defs=[('ui','Trading Workstation',[]),('strategy','Strategy Engine',['market_data','risk','portfolio']),('market_data','Market Data',['database']),('portfolio','Portfolio Engine',['database']),('risk','Risk Engine',['portfolio']),('execution','Execution Engine',['risk','paper_broker']),('paper_broker','Paper Broker',['market_data']),('scanner','Scanner',['market_data','strategy']),('research','Research Services',['database']),('reporting','Reporting',['database']),('database','PostgreSQL',[])]
        services=[]
        for sid,name,deps in defs:
            o=s['service_overrides'].get(sid,{})
            services.append(ServiceHealth(service_id=sid,display_name=name,status=o.get('status','HEALTHY'),heartbeat_at=now,uptime_seconds=time.monotonic(),latency_ms=float(o.get('latency_ms',0)),version=str(o.get('version','33.7.0')),dependencies=deps,details=o.get('details',{})))
        rank={'HEALTHY':0,'DEGRADED':1,'UNKNOWN':2,'UNHEALTHY':3};overall=max((x.status for x in services),key=lambda x:rank[x],default='UNKNOWN')
        return HealthTopology(generated_at=now,overall_status=overall,services=services,edges=[{'from':d,'to':x.service_id} for x in services for d in x.dependencies])
    def request_runtime_control(self,r):
        if 'operations.runtime.request' not in r.actor.permissions: raise PermissionError('Missing operations.runtime.request permission.')
        if not r.confirmation_token.startswith('CONFIRM-OPS-'): raise PermissionError('Invalid operations confirmation token.')
        with self._lock:
            s=self._load();rec=RuntimeControlRecord(request_id='ops-'+uuid4().hex[:16],service_id=r.service_id,action=r.action,requested_at=self._now(),requested_by=r.actor.user_id,reason=r.reason,status='REQUESTED');s['runtime_controls'].append(rec.model_dump(mode='json'));self._save(s);self._audit('RUNTIME_CONTROL_REQUESTED',r.actor,'runtime_control',rec.request_id,None,rec.model_dump(mode='json'));return rec
    def approve_runtime_control(self,rid,r):
        if 'operations.runtime.approve' not in r.actor.permissions: raise PermissionError('Missing operations.runtime.approve permission.')
        if not r.confirmation_token.startswith('CONFIRM-OPS-'): raise PermissionError('Invalid operations confirmation token.')
        with self._lock:
            s=self._load();i=next((i for i,x in enumerate(s['runtime_controls']) if x['request_id']==rid),None)
            if i is None: raise KeyError(rid)
            cur=RuntimeControlRecord.model_validate(s['runtime_controls'][i])
            if cur.requested_by==r.actor.user_id: raise PermissionError('Four-eye approval requires a different user.')
            before=cur.model_dump(mode='json')
            if r.decision=='REJECT': cur.status='REJECTED';cur.verification_message=r.reason
            else: cur.status='APPROVED';cur.approved_by=r.actor.user_id;cur.approved_at=self._now()
            s['runtime_controls'][i]=cur.model_dump(mode='json');self._save(s);self._audit('RUNTIME_CONTROL_APPROVAL',r.actor,'runtime_control',rid,before,cur.model_dump(mode='json'));return cur
    def execute_runtime_control(self,rid,actor):
        if 'operations.runtime.execute' not in actor.permissions: raise PermissionError('Missing operations.runtime.execute permission.')
        with self._lock:
            s=self._load();i=next((i for i,x in enumerate(s['runtime_controls']) if x['request_id']==rid),None)
            if i is None: raise KeyError(rid)
            cur=RuntimeControlRecord.model_validate(s['runtime_controls'][i])
            if cur.status!='APPROVED': raise ValueError('Runtime control must be approved before execution.')
            before=cur.model_dump(mode='json');cur.status='EXECUTED';cur.executed_at=self._now();cur.verification_message='Governed runtime intent recorded; direct process control remains outside the UI boundary.'
            s['service_overrides'].setdefault(cur.service_id,{})['status']='DEGRADED' if cur.action in {'PAUSE','DRAIN','DISABLE'} else 'HEALTHY';s['runtime_controls'][i]=cur.model_dump(mode='json');self._save(s);self._audit('RUNTIME_CONTROL_EXECUTED',actor,'runtime_control',rid,before,cur.model_dump(mode='json'));return cur
    def list_runtime_controls(self): return [RuntimeControlRecord.model_validate(x) for x in self._load()['runtime_controls']]
    def list_incidents(self): return [IncidentRecord.model_validate(x) for x in self._load()['incidents']]
    def list_alerts(self): return [AlertRecord.model_validate(x) for x in self._load()['alerts']]
    def register_release(self,r):
        if 'operations.release.register' not in r.actor.permissions: raise PermissionError('Missing operations.release.register permission.')
        with self._lock:
            s=self._load();rec=ReleaseRecord(release_id='release-'+uuid4().hex[:16],release_version=r.release_version,git_commit=r.git_commit,migration_version=r.migration_version,database_revision=r.database_revision,installer_version=r.installer_version,package_sha256=r.package_sha256.lower(),deployment_time=self._now(),rollback_target=r.rollback_target,approved_by=r.actor.user_id,deployed_by=r.actor.user_id);s['releases'].append(rec.model_dump(mode='json'));self._save(s);self._audit('RELEASE_REGISTERED',r.actor,'release',rec.release_id,None,rec.model_dump(mode='json'));return rec
    def list_releases(self): return [ReleaseRecord.model_validate(x) for x in self._load()['releases']]
    def acquire_lock(self,name,reason,actor,ttl_minutes=30):
        if 'operations.lock.acquire' not in actor.permissions: raise PermissionError('Missing operations.lock.acquire permission.')
        with self._lock:
            s=self._load();now=self._now();active=[OperationalLock.model_validate(x) for x in s['locks'] if x['lock_name']==name and (x.get('expires_at') is None or datetime.fromisoformat(x['expires_at'])>now)]
            if active: raise ValueError(f'Operational lock {name} is already held.')
            lock=OperationalLock(lock_name=name,owner_user_id=actor.user_id,acquired_at=now,expires_at=now+timedelta(minutes=ttl_minutes),reason=reason);s['locks'].append(lock.model_dump(mode='json'));self._save(s);self._audit('OPERATIONAL_LOCK_ACQUIRED',actor,'operational_lock',name,None,lock.model_dump(mode='json'));return lock
    def list_locks(self):
        now=self._now();return [x for x in (OperationalLock.model_validate(v) for v in self._load()['locks']) if x.expires_at is None or x.expires_at>now]
