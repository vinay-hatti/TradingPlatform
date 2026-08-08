from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.live_trading_governance.models import *
from trading_ai.live_trading_governance.service import LiveTradingGovernanceService

def svc():
 e=create_engine('sqlite+pysqlite:///:memory:');Base.metadata.create_all(e);return sessionmaker(bind=e)()

def test_live_disabled_by_default_and_maker_checker():
 s=svc();g=LiveTradingGovernanceService(s);g.create_policy('LIVE-PRIMARY','maker',{'allowed_symbols':['SPY'],'allowed_strategies':['LONG_CALL']});r=g.request_approval('LIVE-PRIMARY','maker')
 assert g.status('LIVE-PRIMARY')['live_routing_enabled'] is False
 try:g.approve(r['approval_id'],'maker');assert False
 except PermissionError:pass
 g.approve(r['approval_id'],'checker');assert g.status('LIVE-PRIMARY')['policy']['status']=='APPROVED'

def test_certification_activation_and_kill_switch_fail_closed():
 s=svc();g=LiveTradingGovernanceService(s);g.create_policy('LIVE-PRIMARY','maker',{'allowed_symbols':['SPY'],'allowed_strategies':['LONG_CALL']});r=g.request_approval('LIVE-PRIMARY','maker');g.approve(r['approval_id'],'checker')
 c=g.certify('LIVE-PRIMARY','checker',{'platform_ready':True,'broker_account_verified':True,'management_ready':True,'kill_switch_tested':True});assert c['status']=='PASSED'
 try:g.activate('LIVE-PRIMARY','checker','bad');assert False
 except ValueError:pass
 st=g.activate('LIVE-PRIMARY','checker','ENABLE LIVE ROUTING FOR LIVE-PRIMARY');assert st['live_routing_enabled'] is True
 h=g.halt('LIVE-PRIMARY','operator','test');assert h['status']=='ACTIVE';assert g.status('LIVE-PRIMARY')['live_routing_enabled'] is False

def test_order_gate_enforces_allowlist_limits_and_readiness():
 s=svc();g=LiveTradingGovernanceService(s);g.create_policy('LIVE-PRIMARY','maker',{'allowed_symbols':['SPY'],'allowed_strategies':['LONG_CALL'],'max_contracts':1});r=g.request_approval('LIVE-PRIMARY','maker');g.approve(r['approval_id'],'checker');g.certify('LIVE-PRIMARY','checker',{'platform_ready':True,'broker_account_verified':True,'management_ready':True,'kill_switch_tested':True});g.activate('LIVE-PRIMARY','checker','ENABLE LIVE ROUTING FOR LIVE-PRIMARY')
 ready={'platform_ready':True,'execution_ready':True,'portfolio_ready':True,'management_ready':True}
 assert g.evaluate_order('LIVE-PRIMARY',{'symbol':'SPY','strategy':'LONG_CALL','order_type':'LMT','quantity':1,'maximum_loss_pct':.25},ready)['allowed']
 bad=g.evaluate_order('LIVE-PRIMARY',{'symbol':'AAPL','strategy':'LONG_CALL','order_type':'MKT','quantity':2,'maximum_loss_pct':2},ready);assert not bad['allowed'];assert 'SYMBOL_NOT_ALLOWED' in bad['reasons'];assert 'ORDER_TYPE_NOT_ALLOWED' in bad['reasons']
