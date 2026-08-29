from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.execution_workspace.models import ExecutionIntentModel,ExecutionIntentAuditModel
from trading_ai.execution_workspace.service import ExecutionWorkspaceService
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel,BrokerOrderControlModel,BrokerAccountSnapshotModel

def main():
 engine=create_engine('sqlite+pysqlite:///:memory:')
 # Create only tables required for creation/lifecycle contract.
 for table in (TradePlanModel.__table__,BrokerAccountBindingModel.__table__,BrokerOrderControlModel.__table__,BrokerAccountSnapshotModel.__table__,ExecutionIntentModel.__table__,ExecutionIntentAuditModel.__table__):table.create(engine)
 Session=sessionmaker(bind=engine,expire_on_commit=False);s=Session();ts='2026-08-03T16:00:00+00:00'
 s.add(BrokerAccountBindingModel(binding_id='B1',portfolio_id='PAPER-PRIMARY',broker_name='INTERACTIVE_BROKERS',broker_environment='PAPER',broker_account_id='DU123',base_currency='USD',host='127.0.0.1',port=7497,client_id=50,read_only=False,live_trading_enabled=False,status='VERIFIED_PAPER_TRADING',created_at=ts,updated_at=ts,metadata_json={}))
 s.add(BrokerOrderControlModel(portfolio_id='PAPER-PRIMARY',paper_order_submission_enabled=True,activation_token_hash='x',activated_at=ts,activated_by='test',disabled_at=None,disable_reason='',version=1,updated_at=ts,metadata_json={'paper_only':True}))
 s.add(BrokerAccountSnapshotModel(snapshot_id='S1',binding_id='B1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',captured_at=ts,base_currency='USD',net_liquidation=100000,total_cash_value=90000,available_funds=80000,buying_power=200000,excess_liquidity=70000,raw_json={}))
 s.add(TradePlanModel(trade_plan_id='TP1',opportunity_id='OP1',opportunity_version=2,intelligence_id='II1',account_id='PAPER-PRIMARY',symbol='AAPL',direction='CALL',strategy='LONG_CALL',state='PAPER_READY',version=3,capital=100000,risk_budget_pct=1,risk_budget_amount=1000,estimated_debit=250,estimated_credit=0,max_loss=250,max_profit=None,reward_risk_ratio=None,net_greeks_json={},validation_json={'valid':True,'defined_risk':True},legs_json=[{'side':'BUY','quantity':1,'option_right':'CALL','strike':250,'expiry':'2026-09-18','limit_price':2.5,'option_symbol':'AAPL  260918C00250000'}],execution_intent_json={},notes='',created_by='test',created_at=ts,updated_at=ts))
 s.commit();svc=ExecutionWorkspaceService(s);x=svc.create_from_trade_plan('TP1','test')
 assert x['state']=='VALIDATED';assert x['validation']['valid'] is True;assert x['validation']['buying_power']==200000
 y=svc.transition(x['execution_intent_id'],x['version'],'APPROVED','test','review complete');assert y['state']=='APPROVED';assert y['version']==2
 assert svc.create_from_trade_plan('TP1','test')['execution_intent_id']==x['execution_intent_id']
 events=svc.repo.audit(x['execution_intent_id']);assert len(events)==2
 try:svc.transition(x['execution_intent_id'],2,'FILLED','test','invalid shortcut')
 except ValueError:pass
 else:raise AssertionError('invalid lifecycle shortcut accepted')
 print('Milestone 59 Institutional Execution Workspace assertions passed.')
if __name__=='__main__':main()
