from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import uuid4
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from .models import *

def utcnow(): return datetime.now(timezone.utc)
def iso(dt=None): return (dt or utcnow()).isoformat()
def parse_dt(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:return None

def _id(prefix): return f'{prefix}-{uuid4().hex.upper()}'

def json_safe(value):
    """Recursively normalize operational payloads for JSON/JSONB persistence and API output."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value

SERVICE_DEFS=[
 ('postgresql','PostgreSQL','CORE',True,[]),('production_api','Production API','CORE',True,['postgresql']),
 ('polygon','Polygon Data Provider','PROVIDER',True,[]),('ibkr_gateway','IBKR Gateway','PROVIDER',True,[]),
 ('underlying_ingestion','Underlying Ingestion','INGESTION',True,['polygon','postgresql']),
 ('options_ingestion','Options Ingestion','INGESTION',True,['polygon','underlying_ingestion']),
 ('stock_intelligence','Stock Intelligence','INTELLIGENCE',True,['underlying_ingestion']),
 ('inflection_intelligence','Inflection Intelligence','INTELLIGENCE',True,['stock_intelligence','options_ingestion']),
 ('institutional_options','Institutional Options','DECISION',True,['stock_intelligence','options_ingestion']),
 ('option_valuation_intelligence','Option Valuation Intelligence','INTELLIGENCE',True,['institutional_options','inflection_intelligence','options_ingestion']),
 ('broker_sync','Broker Portfolio Sync','PORTFOLIO',True,['ibkr_gateway','postgresql']),
 ('dynamic_management','Dynamic Position Management','MANAGEMENT',True,['broker_sync','institutional_options']),
 ('portfolio_intelligence','Portfolio Risk & Allocation','PORTFOLIO',True,['broker_sync','institutional_options']),
 ('performance_learning','Performance Learning','LEARNING',False,['portfolio_intelligence']),
 ('live_governance','Live Trading Governance','GOVERNANCE',True,['production_api','portfolio_intelligence','dynamic_management']),
 ('workstation','Institutional Workstation','UI',False,['production_api']),
]

PUBLICATIONS=[
 {'name':'current_market_state','table':'market_ingestion_publication','ts':'published_at','max_age':86400,'filter_col':'publication_name','filter_value':'current_market_state','id_cols':('run_id','publication_name')},
 {'name':'current_institutional_inflection','table':'institutional_inflection_publications','ts':'published_at','max_age':86400,'filter_col':'publication_name','filter_value':'current_institutional_inflection','id_cols':('publication_id','source_run_id')},
 {'name':'current_option_valuation_intelligence','table':'institutional_option_valuation_publications','ts':'published_at','max_age':1800,'filter_col':'publication_name','filter_value':'current_option_valuation_intelligence','id_cols':('publication_id',)},
 {'name':'current_stock_intelligence','table':'stock_scanner_publications','ts':'snapshot_timestamp','max_age':86400,'filter_col':'publication_name','filter_value':'current_stock_intelligence','id_cols':('scanner_run_id','id')},
 {'name':'current_broker_portfolio','table':'broker_portfolio_publications','ts':'published_at','max_age':600,'filter_col':'publication_name','filter_value':'current_broker_portfolio','id_cols':('publication_id','portfolio_id')},
 {'name':'current_portfolio_allocation','table':'portfolio_allocation_publications','ts':'published_at','max_age':1800,'filter_col':'publication_name','filter_value':'current_portfolio_allocation','id_cols':('publication_id','portfolio_id')},
 {'name':'current_performance_learning','table':'performance_learning_publications','ts':'published_at','max_age':7200,'filter_col':'publication_name','filter_value':'current_performance_learning','id_cols':('publication_id','report_id')},
]
SERVICE_FRESHNESS={
 'underlying_ingestion':86400,
 'options_ingestion':1800,
 'stock_intelligence':86400,
 'inflection_intelligence':86400,
 'option_valuation_intelligence':1800,
 'broker_sync':600,
 'portfolio_intelligence':1800,
 'performance_learning':7200,
}

class ProductionOperationsService:
 def __init__(self,session:Session,root:Path|None=None): self.s=session;self.root=root or Path(__file__).resolve().parents[3]
 def audit(self,etype,eid,event,actor='system',**payload):
  self.s.add(OpsAuditEventModel(event_id=_id('M66-EVT'),entity_type=etype,entity_id=eid,event_type=event,actor=actor,occurred_at=iso(),payload_json=json_safe(payload)))
 def bootstrap(self):
  now=iso()
  for sid,name,domain,critical,deps in SERVICE_DEFS:
   row=self.s.get(OpsServiceModel,sid)
   if not row:self.s.add(OpsServiceModel(service_id=sid,name=name,domain=domain,status='UNKNOWN',critical=critical,dependencies_json=deps,metadata_json={},updated_at=now))
  self.s.commit();return len(SERVICE_DEFS)
 def _table(self,name): return inspect(self.s.bind).has_table(name)
 def _latest(self,table,tscol,filter_col=None,filter_value=None):
  if not self._table(table):return None
  try:
   where=f' WHERE {filter_col} = :filter_value' if filter_col else ''
   return self.s.execute(text(f'SELECT * FROM {table}{where} ORDER BY {tscol} DESC LIMIT 1'), {'filter_value':filter_value} if filter_col else {}).mappings().first()
  except Exception:self.s.rollback();return None
 def _age_status(self,row,tscol,max_age,missing='No successful run or publication found'):
  if not row:return 'STALE',{'reason':missing,'maximum_age_seconds':max_age,'age_seconds':None,'last_success_at':None}
  dt=parse_dt(row.get(tscol)); age=max(0.0,(utcnow()-dt).total_seconds()) if dt else None
  status='READY' if age is not None and age<=max_age else 'STALE'
  remaining=max(0,max_age-age) if age is not None else None
  reason=(f'age={age:.0f}s; policy={max_age}s; remaining={remaining:.0f}s' if status=='READY' else f'age={age:.0f}s exceeds policy={max_age}s by {age-max_age:.0f}s') if age is not None else 'Latest timestamp is missing or invalid'
  return status,{'reason':reason,'maximum_age_seconds':max_age,'age_seconds':age,'freshness_remaining_seconds':remaining,'last_success_at':iso(dt) if dt else None}
 def _service_status(self,sid):
  now=utcnow(); meta={}; status='READY';lat=None
  try:
   start=time.perf_counter()
   if sid=='postgresql': self.s.execute(text('SELECT 1'))
   elif sid=='production_api': status='READY' if Path(self.root/'src/trading_ai/production_api/app.py').exists() else 'FAILED'
   elif sid=='workstation': status='READY' if Path(self.root/'ui/workstation/src').exists() else 'FAILED'
   elif sid=='polygon':
    configured=bool(os.getenv('POLYGON_API_KEY') or os.getenv('POLYGON_KEY'))
    if configured: status='READY';meta.update(reason='API credentials configured',recommended_action='None')
    else: status='DEGRADED';meta.update(reason='Polygon API key environment variable not detected by the API process',recommended_action='Set POLYGON_API_KEY for the API/daemon process and refresh readiness')
   elif sid=='ibkr_gateway':
    row=self._latest('broker_account_snapshots','captured_at');status='READY' if row else 'DEGRADED';meta.update(latest_snapshot=dict(row) if row else None,reason='Latest broker account snapshot available' if row else 'No broker account snapshot found',recommended_action='Run Milestone 63 broker synchronization' if not row else 'None')
   elif sid=='underlying_ingestion': status,meta=self._age_status(self._latest('price_history','date'),'date',SERVICE_FRESHNESS[sid])
   elif sid=='options_ingestion':
    row=self._latest('option_contract_snapshots','snapshot_timestamp') or self._latest('historical_option_quotes','timestamp'); col='snapshot_timestamp' if row and row.get('snapshot_timestamp') is not None else 'timestamp';status,meta=self._age_status(row,col,SERVICE_FRESHNESS[sid])
   elif sid=='stock_intelligence': status,meta=self._age_status(self._latest('stock_scanner_publications','snapshot_timestamp','publication_name','current_stock_intelligence'),'snapshot_timestamp',SERVICE_FRESHNESS[sid])
   elif sid=='inflection_intelligence': status,meta=self._age_status(self._latest('institutional_inflection_publications','published_at','publication_name','current_institutional_inflection'),'published_at',SERVICE_FRESHNESS[sid])
   elif sid=='option_valuation_intelligence': status,meta=self._age_status(self._latest('institutional_option_valuation_publications','published_at','publication_name','current_option_valuation_intelligence'),'published_at',SERVICE_FRESHNESS[sid])
   elif sid=='institutional_options': status='READY' if self._latest('institutional_option_decision_snapshots','created_at') else 'DEGRADED';meta['reason']='Decision snapshots available' if status=='READY' else 'No Institutional Options decision snapshot found'
   elif sid=='broker_sync': status,meta=self._age_status(self._latest('broker_portfolio_publications','published_at','publication_name','current_broker_portfolio'),'published_at',SERVICE_FRESHNESS[sid])
   elif sid=='dynamic_management': status='READY' if self._table('managed_positions') else 'FAILED'
   elif sid=='portfolio_intelligence': status,meta=self._age_status(self._latest('portfolio_allocation_publications','published_at','publication_name','current_portfolio_allocation'),'published_at',SERVICE_FRESHNESS[sid])
   elif sid=='performance_learning':
    status,meta=self._age_status(self._latest('performance_learning_publications','published_at','publication_name','current_performance_learning'),'published_at',SERVICE_FRESHNESS[sid]);status='DEGRADED' if status=='STALE' and meta.get('last_success_at') is None else status
   lat=(time.perf_counter()-start)*1000
  except Exception as e: self.s.rollback();status='FAILED';meta['error']=f'{type(e).__name__}: {e}'
  return status,lat,meta
 def refresh_services(self):
  self.bootstrap(); now=iso();out=[]
  for row in self.s.scalars(select(OpsServiceModel)).all():
   status,lat,meta=self._service_status(row.service_id);row.status=status;row.heartbeat_at=now;row.latency_ms=lat;row.updated_at=now;row.metadata_json=json_safe({**(row.metadata_json or {}),**meta})
   if status=='READY':row.last_success_at=now
   elif status=='FAILED':row.last_failure_at=now
   out.append(self.service_dto(row))
  self.s.commit();return out
 def evaluate_freshness(self):
  now=utcnow();results=[]
  for spec in PUBLICATIONS:
   pub,table,tscol,maxage=spec['name'],spec['table'],spec['ts'],spec['max_age']
   row=self._latest(table,tscol,spec.get('filter_col'),spec.get('filter_value'))
   source='missing'
   if row:
    for col in spec.get('id_cols',()):
     if row.get(col):source=str(row.get(col));break
   dt=parse_dt(row.get(tscol)) if row else None;age=max(0.0,(now-dt).total_seconds()) if dt else None
   status='READY' if age is not None and age<=maxage else ('STALE' if row else 'FAILED')
   remaining=max(0,maxage-age) if age is not None else None
   if status=='READY':reason=f'age={age:.0f}s; policy={maxage}s; remaining={remaining:.0f}s'
   elif row and age is not None:reason=f'age={age:.0f}s exceeds policy={maxage}s by {age-maxage:.0f}s; last successful publication={iso(dt)}'
   elif row:reason=f'Publication exists in {table}, but {tscol} is missing or invalid'
   else:reason=f'No {pub} row found in authoritative table {table}'
   existing=self.s.scalar(select(OpsPublicationFreshnessModel).where(OpsPublicationFreshnessModel.publication_name==pub,OpsPublicationFreshnessModel.source_id==source))
   lineage=dict(row) if row else {};lineage.update({'authoritative_table':table,'timestamp_column':tscol,'freshness_remaining_seconds':remaining})
   values=dict(status=status,published_at=iso(dt) if dt else None,age_seconds=age,maximum_age_seconds=maxage,reason=reason,lineage_json=json_safe(lineage),evaluated_at=iso(now))
   if existing:
    for k,v in values.items():setattr(existing,k,v)
    obj=existing
   else:obj=OpsPublicationFreshnessModel(freshness_id=_id('M66-FRESH'),publication_name=pub,source_id=source,**values);self.s.add(obj)
   results.append({'publication_name':pub,'status':status,'age_seconds':age,'maximum_age_seconds':maxage,'freshness_remaining_seconds':remaining,'published_at':iso(dt) if dt else None,'reason':reason,'source_id':source,'authoritative_table':table})
  self.s.commit();return results
 def readiness(self,persist=True):
  services=self.refresh_services();fresh=self.evaluate_freshness();sm={x['service_id']:x['status'] for x in services};fm={x['publication_name']:x['status'] for x in fresh}
  gates={
   'scanner_ready': sm.get('underlying_ingestion')=='READY' and fm.get('current_stock_intelligence')=='READY',
   'decision_ready': sm.get('institutional_options')=='READY' and sm.get('options_ingestion')=='READY' and sm.get('inflection_intelligence')=='READY' and sm.get('option_valuation_intelligence')=='READY' and fm.get('current_institutional_inflection')=='READY' and fm.get('current_option_valuation_intelligence')=='READY',
   'execution_ready': sm.get('ibkr_gateway')=='READY' and sm.get('institutional_options')=='READY',
   'management_ready': sm.get('dynamic_management')=='READY' and sm.get('broker_sync')=='READY',
   'portfolio_ready': sm.get('portfolio_intelligence')=='READY' and fm.get('current_broker_portfolio')=='READY',
   'learning_ready': sm.get('performance_learning') in ('READY','DEGRADED'),
  };gates['platform_ready']=all(gates[k] for k in ('scanner_ready','decision_ready','execution_ready','management_ready','portfolio_ready'))
  status='READY' if gates['platform_ready'] else ('DEGRADED' if any(gates.values()) else 'FAILED');payload={'status':status,**gates,'services':services,'freshness':fresh,'evaluated_at':iso()}
  if persist:
   p=OpsReadinessPublicationModel(publication_id=_id('M66-READY'),publication_name='current_platform_readiness',status=status,published_at=iso(),payload_json=json_safe(payload),**gates);self.s.add(p);self.s.commit()
  self.reconcile_alerts(payload);return payload
 def reconcile_alerts(self,payload):
  active=[]
  for svc in payload['services']:
   if svc['critical'] and svc['status']!='READY':active.append((f"service:{svc['service_id']}",'CRITICAL' if svc['status']=='FAILED' else 'WARNING','SERVICE',f"{svc['name']} is {svc['status']}",f"Restore {svc['name']} and rerun readiness."))
  for p in payload['freshness']:
   if p['status']!='READY':active.append((f"publication:{p['publication_name']}",'WARNING','FRESHNESS',f"{p['publication_name']} is {p['status']}",f"Rebuild {p['publication_name']} through its owning workflow."))
  fingerprints={a[0] for a in active};now=iso()
  for fp,severity,cat,title,action in active:
   row=self.s.scalar(select(OpsAlertModel).where(OpsAlertModel.fingerprint==fp,OpsAlertModel.status=='OPEN'))
   if row:row.updated_at=now;row.message=title
   else:self.s.add(OpsAlertModel(alert_id=_id('M66-ALERT'),fingerprint=fp,severity=severity,status='OPEN',category=cat,title=title,message=title,owner='platform-operations',recommended_action=action,created_at=now,updated_at=now,payload_json=json_safe({})))
  for row in self.s.scalars(select(OpsAlertModel).where(OpsAlertModel.status=='OPEN')).all():
   if row.fingerprint not in fingerprints:row.status='RESOLVED';row.updated_at=now
  self.s.commit()
 def dependency_graph(self,services=None):
  rows=services or [self.service_dto(x) for x in self.s.scalars(select(OpsServiceModel)).all()]
  nodes=[{'id':r['service_id'],'label':r['name'],'domain':r['domain'],'status':r['status'],'reason':(r.get('metadata_json') or {}).get('reason'),'recommended_action':(r.get('metadata_json') or {}).get('recommended_action')} for r in rows]
  edges=[]
  for r in rows:
   for dep in r.get('dependencies_json') or []:edges.append({'source':dep,'target':r['service_id']})
  return {'nodes':nodes,'edges':edges}
 def dashboard(self):
  errors={};ready={};alerts=[];runs=[];locks=[]
  try:ready=self.readiness()
  except Exception as e:self.s.rollback();errors['readiness']=f'{type(e).__name__}: {e}'
  try:alerts=[self.alert_dto(x) for x in self.s.scalars(select(OpsAlertModel).order_by(OpsAlertModel.created_at.desc()).limit(100)).all()]
  except Exception as e:self.s.rollback();errors['alerts']=f'{type(e).__name__}: {e}'
  try:runs=[self.enriched_run_dto(x) for x in self.s.scalars(select(OpsWorkflowRunModel).order_by(OpsWorkflowRunModel.started_at.desc()).limit(25)).all()]
  except Exception as e:self.s.rollback();errors['workflow_runs']=f'{type(e).__name__}: {e}'
  try:locks=[self.lock_dto(x) for x in self.s.scalars(select(OpsLockModel)).all()]
  except Exception as e:self.s.rollback();errors['locks']=f'{type(e).__name__}: {e}'
  services=ready.get('services') or []
  return json_safe({'readiness':ready,'alerts':alerts,'workflow_runs':runs,'locks':locks,'dependency_graph':self.dependency_graph(services),'component_errors':errors,'generated_at':iso()})
 def workflow_plan(self):
  return [
   ('preflight',None),('underlying_ingestion','scripts/ingest_underlying_data.py'),('options_ingestion','scripts/ingest_options_data.py'),('broker_sync','scripts/run_m63_broker_portfolio_sync.py'),('dynamic_management','scripts/run_m62_dynamic_position_management.py'),('portfolio_intelligence','scripts/run_m64_portfolio_intelligence.py'),('performance_learning','scripts/run_m65_performance_learning.py'),('readiness',None)]
 def run_workflow(self,mode='SIMULATION',actor='operator',continue_on_error=False):
  run=OpsWorkflowRunModel(run_id=_id('M66-RUN'),workflow_name='daily-production-cycle',mode=mode,status='RUNNING',started_at=iso(),actor=actor,stage_results_json=json_safe([]),metadata_json=json_safe({}));self.s.add(run);self.s.commit();results=[]
  for stage,path in self.workflow_plan():
   run.current_stage=stage;self.s.commit();start=time.perf_counter()
   try:
    if stage in ('preflight','readiness'):detail=self.readiness()
    elif mode=='SIMULATION':detail={'command':path,'exists':(self.root/path).exists(),'would_execute':True};
    else:
     if not (self.root/path).exists():raise FileNotFoundError(path)
     cp=subprocess.run([sys.executable,str(self.root/path)],cwd=self.root,text=True,capture_output=True,timeout=7200);detail={'returncode':cp.returncode,'stdout':cp.stdout[-4000:],'stderr':cp.stderr[-4000:]};
     if cp.returncode:raise RuntimeError(f'{stage} exited {cp.returncode}')
    item={'stage':stage,'status':'READY','duration_ms':round((time.perf_counter()-start)*1000,2),'detail':detail}
   except Exception as e:
    item={'stage':stage,'status':'FAILED','duration_ms':round((time.perf_counter()-start)*1000,2),'error':f'{type(e).__name__}: {e}'}
    results.append(item);run.stage_results_json=json_safe(results);run.status='FAILED';run.error=item['error'];self.s.commit()
    if not continue_on_error:break
    continue
   results.append(item);run.stage_results_json=json_safe(results);self.s.commit()
  if run.status!='FAILED':run.status='READY';run.finished_at=iso();run.current_stage=None;run.stage_results_json=json_safe(results);self.audit('WORKFLOW',run.run_id,'WORKFLOW_COMPLETED',actor,status=run.status,mode=mode);self.s.commit()
  return json_safe(self.run_dto(run))
 def acknowledge(self,alert_id,actor):
  row=self.s.get(OpsAlertModel,alert_id)
  if not row:raise KeyError(alert_id)
  row.status='ACKNOWLEDGED';row.acknowledged_at=iso();row.acknowledged_by=actor;row.updated_at=iso();self.audit('ALERT',alert_id,'ALERT_ACKNOWLEDGED',actor);self.s.commit();return self.alert_dto(row)
 def recover(self,action,target_type,target_id,actor,reason):
  row=OpsRecoveryActionModel(recovery_id=_id('M66-REC'),action_type=action,target_type=target_type,target_id=target_id,status='RUNNING',actor=actor,reason=reason,started_at=iso(),result_json={});self.s.add(row);self.s.commit()
  try:
   result={}
   if action=='RECOVER_STALE_LOCKS':
    now=utcnow();locks=self.s.scalars(select(OpsLockModel)).all();removed=[]
    for l in locks:
     if (parse_dt(l.expires_at) or now)<=now:removed.append(l.lock_name);self.s.delete(l)
    result={'removed':removed}
   elif action=='REFRESH_READINESS':result=self.readiness()
   elif action=='RETRY_WORKFLOW':result=self.run_workflow('SIMULATION',actor)
   else:result={'status':'RECORDED','message':'Action requires operator-specific execution.'}
   row.status='READY';row.result_json=json_safe(result)
  except Exception as e:row.status='FAILED';row.result_json=json_safe({'error':f'{type(e).__name__}: {e}'})
  row.finished_at=iso();self.audit('RECOVERY',row.recovery_id,'RECOVERY_COMPLETED',actor,status=row.status);self.s.commit();return json_safe({'recovery_id':row.recovery_id,'status':row.status,'result':row.result_json})
 def enriched_run_dto(self,x):
  data=self.run_dto(x); started=parse_dt(x.started_at);finished=parse_dt(x.finished_at);results=x.stage_results_json or []
  data['duration_ms']=round((finished-started).total_seconds()*1000,2) if started and finished else round(sum(float(i.get('duration_ms') or 0) for i in results),2)
  data['stage_count']=len(results);data['failed_stage_count']=sum(1 for i in results if i.get('status')=='FAILED')
  data['retry_count']=int((x.metadata_json or {}).get('retry_count',0));data['outputs']=[i.get('stage') for i in results if i.get('status')=='READY']
  processed=0
  for i in results:
   detail=i.get('detail') or {}
   for key in ('processed','requested','persisted','generated','optimized','refreshed','created'):
    value=detail.get(key)
    if isinstance(value,(int,float)):processed+=int(value)
  data['records_processed']=processed
  return data
 @staticmethod
 def service_dto(x):return json_safe({c.name:getattr(x,c.name) for c in x.__table__.columns})
 @staticmethod
 def alert_dto(x):return json_safe({c.name:getattr(x,c.name) for c in x.__table__.columns})
 @staticmethod
 def run_dto(x):return json_safe({c.name:getattr(x,c.name) for c in x.__table__.columns})
 @staticmethod
 def lock_dto(x):return json_safe({c.name:getattr(x,c.name) for c in x.__table__.columns})
