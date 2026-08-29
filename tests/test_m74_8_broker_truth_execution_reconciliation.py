from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.broker.ibkr.database_models import BrokerOrderModel, BrokerPositionSnapshotModel
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.base import Base
from trading_ai.execution_workspace.models import ExecutionIntentAuditModel, ExecutionIntentModel

TS='2026-08-11T16:55:00+00:00'
TS2='2026-08-11T17:00:00+00:00'


def _Session(tmp_path):
    engine=create_engine(f"sqlite+pysqlite:///{tmp_path/'m748.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)


def _legs():
    return [
        {'side':'BUY','quantity':1,'option_right':'CALL','strike':720.0,'expiry':'2026-10-30','option_symbol':'O:QQQ261030C00720000'},
        {'side':'SELL','quantity':1,'option_right':'CALL','strike':745.0,'expiry':'2026-09-11','option_symbol':'O:QQQ260911C00745000'},
    ]


def _seed(Session, *, state='REJECTED', order_status='FILLED', second_filled_retry=False):
    with Session() as s:
        s.add(TradePlanModel(trade_plan_id='TP1',opportunity_id='OP1',opportunity_version=1,intelligence_id='I1',account_id='PAPER-PRIMARY',symbol='QQQ',direction='BULLISH',strategy='CALL_DIAGONAL',state='PAPER_READY',version=2,capital=1_000_000,risk_budget_pct=5,risk_budget_amount=50_000,estimated_debit=1.03,estimated_credit=0,max_loss=103,max_profit=None,reward_risk_ratio=None,net_greeks_json={},validation_json={'valid':True},legs_json=_legs(),execution_intent_json={'dynamic_management':{'underlying_stop':700,'underlying_targets':[730,740,750]}},notes='',created_by='test',created_at=TS,updated_at=TS))
        for attempt, xi, broker_id in [(1,'XI1',47)]+([(2,'XI2',48)] if second_filled_retry else []):
            s.add(ExecutionIntentModel(execution_intent_id=xi,trade_plan_id='TP1',trade_plan_version=2,execution_attempt=attempt,parent_execution_intent_id='XI1' if attempt>1 else None,retry_reason='retry' if attempt>1 else None,opportunity_id='OP1',portfolio_id='PAPER-PRIMARY',account_id='PAPER-PRIMARY',symbol='QQQ',strategy='CALL_DIAGONAL',state=state,version=2,max_loss=103,legs_json=_legs(),order_request_json={},validation_json={'valid':True},broker_json={},metadata_json={'dynamic_management':{'underlying_stop':700,'underlying_targets':[730,740,750]}},created_by='test',created_at=TS,updated_at=TS,submitted_at=TS,terminal_at=TS))
            s.add(BrokerOrderModel(broker_order_record_id=f'BOR{broker_id}',binding_id='B1',portfolio_id='PAPER-PRIMARY',aggregate_id=f'M59-{xi}',client_order_id=f'M59-CLIENT-{xi}',broker_account_id='DU123',broker_order_id=broker_id,permanent_id=1000+broker_id,api_client_id=50,symbol='QQQ',security_type='BAG',side='BUY',quantity=1,order_type='LMT',time_in_force='DAY',limit_price=1.0,stop_price=None,status=order_status,filled_quantity=1 if order_status=='FILLED' else 0,remaining_quantity=0 if order_status=='FILLED' else 1,average_fill_price=1.0 if order_status=='FILLED' else 0,submitted_at=TS,updated_at=TS2,last_error='',raw_json={'request':{'metadata':{'execution_intent_id':xi}}}))
        for cid,local,qty,strike,expiry in [(905257931,'QQQ   261030C00720000',1,720.0,'20261030'),(907141164,'QQQ   260911C00745000',-1,745.0,'20260911')]:
            s.add(BrokerPositionSnapshotModel(snapshot_position_id=f'SP{cid}',account_snapshot_id='S1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',contract_id=cid,symbol='QQQ',local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',quantity=qty,average_cost=100,expiry=expiry,strike=strike,right='C',multiplier=100,captured_at=TS2,raw_json={}))
            s.add(BrokerCurrentPositionModel(broker_position_id=f'BCP{cid}',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU123',account_snapshot_id='S1',contract_id=cid,symbol='QQQ',local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',signed_quantity=qty,average_cost=1.0,market_price=1.0,market_value=100,unrealized_pnl=0,realized_pnl=0,expiry=expiry,strike=strike,right='C',multiplier=100,active=True,provenance='BROKER_DISCOVERED',reconciliation_status='BROKER_DISCOVERED',portfolio_position_id=None,managed_position_id=None,first_seen_at=TS2,last_seen_at=TS2,closed_at=None,raw_json={}))
        s.commit()


def _recover(s):
    snaps=list(s.scalars(select(BrokerPositionSnapshotModel)).all())
    current=list(s.scalars(select(BrokerCurrentPositionModel)).all())
    return BrokerPortfolioSynchronizationService._recover_platform_intent_lineages(s,'PAPER-PRIMARY',snaps,current)


def test_rejected_execution_is_reconciled_to_filled_when_exact_broker_order_is_filled(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='REJECTED',order_status='FILLED')
    with Session() as s:
        recovered=_recover(s)
        assert set(recovered)=={905257931,907141164}
        intent=s.get(ExecutionIntentModel,'XI1')
        assert intent.state=='FILLED'
        audit=s.scalar(select(ExecutionIntentAuditModel).where(ExecutionIntentAuditModel.execution_intent_id=='XI1'))
        assert audit.event_type=='BROKER_FILLED_AFTER_LOCAL_REJECTION'
        assert audit.previous_state=='REJECTED' and audit.new_state=='FILLED'
        assert audit.payload_json['broker_order_id']==47
        assert audit.payload_json['broker_order_status']=='FILLED'
        assert intent.broker_json['m74_8_broker_truth_reconciliation']['broker_truth_overrode_local_terminal_state'] is True


def test_rejected_execution_without_filled_broker_truth_cannot_recover(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='REJECTED',order_status='REJECTED')
    with Session() as s:
        assert _recover(s)=={}
        assert s.get(ExecutionIntentModel,'XI1').state=='REJECTED'


def test_two_filled_retry_intents_for_same_trade_plan_remain_ambiguous(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='REJECTED',order_status='FILLED',second_filled_retry=True)
    with Session() as s:
        assert _recover(s)=={}
        assert s.get(ExecutionIntentModel,'XI1').state=='REJECTED'
        assert s.get(ExecutionIntentModel,'XI2').state=='REJECTED'
