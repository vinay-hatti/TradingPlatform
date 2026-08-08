from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.production_operations.service import ProductionOperationsService

def svc():
 e=create_engine('sqlite+pysqlite:///:memory:');Base.metadata.create_all(e);return ProductionOperationsService(sessionmaker(bind=e)())
def test_registry_and_readiness_contract():
 s=svc(); assert s.bootstrap()>=10; d=s.readiness(); assert 'platform_ready' in d; assert len(d['services'])>=10
def test_simulation_never_executes_external_commands():
 s=svc(); r=s.run_workflow('SIMULATION','test'); assert r['status']=='READY'; assert all(x['status']=='READY' for x in r['stage_results_json'])
def test_alert_ack_and_recovery():
 s=svc();d=s.dashboard();
 if d['alerts']:
  a=s.acknowledge(d['alerts'][0]['alert_id'],'test');assert a['status']=='ACKNOWLEDGED'
 r=s.recover('RECOVER_STALE_LOCKS','PLATFORM','PLATFORM','test','test');assert r['status']=='READY'

def test_authoritative_publication_lookup_and_dependency_graph():
 s=svc();
 s.s.execute(__import__('sqlalchemy').text("CREATE TABLE market_ingestion_publication (publication_name TEXT, run_id TEXT, published_at TEXT)"))
 from datetime import datetime, timezone
 now=datetime.now(timezone.utc).isoformat()
 s.s.execute(__import__('sqlalchemy').text("INSERT INTO market_ingestion_publication VALUES ('current_market_state','market-run',:now)"),{'now':now})
 from trading_ai.stock_intelligence.models import StockScannerPublicationModel
 StockScannerPublicationModel.__table__.create(bind=s.s.get_bind(), checkfirst=True)
 s.s.add(StockScannerPublicationModel(id='pub-1',symbol='ALL',scanner_run_id='stock-run',candidate_id=None,snapshot_timestamp=now,payload_json={},publication_name='current_stock_intelligence',status='READY'));s.s.commit()
 fresh={x['publication_name']:x for x in s.evaluate_freshness()}
 assert fresh['current_market_state']['status']=='READY'
 assert fresh['current_stock_intelligence']['status']=='READY'
 graph=s.dashboard()['dependency_graph'];assert graph['nodes'];assert graph['edges']

def test_workflow_history_exposes_operational_metrics():
 s=svc();s.run_workflow('SIMULATION','test');run=s.dashboard()['workflow_runs'][0]
 assert run['duration_ms']>=0
 assert run['stage_count']>=1
 assert 'outputs' in run and 'records_processed' in run and 'retry_count' in run

def test_recursive_json_normalization_for_publication_lineage():
 from datetime import date, datetime, timezone
 from decimal import Decimal
 from trading_ai.production_operations.service import json_safe
 value={
  'published_at':datetime(2026,8,5,16,15,34,tzinfo=timezone.utc),
  'business_date':date(2026,8,5),
  'amount':Decimal('12.50'),
  'nested':[{'at':datetime(2026,8,5,16,16,tzinfo=timezone.utc)}],
 }
 normalized=json_safe(value)
 assert normalized['published_at']=='2026-08-05T16:15:34+00:00'
 assert normalized['business_date']=='2026-08-05'
 assert normalized['amount']==12.5
 assert normalized['nested'][0]['at']=='2026-08-05T16:16:00+00:00'



def test_json_normalization_persists_in_ops_json_column():
 from datetime import datetime, timezone
 from trading_ai.production_operations.models import OpsPublicationFreshnessModel
 from trading_ai.production_operations.service import json_safe
 s=svc()
 now=datetime.now(timezone.utc)
 row=OpsPublicationFreshnessModel(
  freshness_id='fresh-json-safe',
  publication_name='current_market_state',
  source_id='market-run',
  status='READY',
  published_at=now.isoformat(),
  age_seconds=0.0,
  maximum_age_seconds=86400,
  reason='test',
  lineage_json=json_safe({'published_at':now,'nested':[{'evaluated_at':now}]}),
  evaluated_at=now.isoformat(),
 )
 s.s.add(row);s.s.commit()
 saved=s.s.get(OpsPublicationFreshnessModel,'fresh-json-safe')
 assert saved.lineage_json['published_at']==now.isoformat()
 assert saved.lineage_json['nested'][0]['evaluated_at']==now.isoformat()
