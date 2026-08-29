from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.broker.ibkr.database_models import BrokerOrderModel, BrokerPositionSnapshotModel
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.base import Base
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager
from trading_ai.execution_workspace.models import ExecutionIntentAuditModel, ExecutionIntentModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TS='2026-08-12T15:00:00+00:00'
TS2='2026-08-12T15:05:00+00:00'


def _Session(tmp_path):
    engine=create_engine(f"sqlite+pysqlite:///{tmp_path/'m7413.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)


def _leg():
    return [{'side':'BUY','quantity':1,'option_right':'CALL','strike':160.0,'expiry':'2026-09-18','option_symbol':'O:TPR260918C00160000'}]


def _seed(Session, *, state='CANCELLED', order_status='FILLED'):
    mg={'underlying_stop':155.0,'underlying_targets':[165.0,170.0,175.0],'theta_exit_days_to_expiry':5,'volatility_exit_rule':'EXIT_ON_IV_COLLAPSE','emergency_option_stop_pct':0.55,'partial_profit_fraction':0.33}
    with Session() as s:
        s.add(TradePlanModel(trade_plan_id='TP1',opportunity_id='OP1',opportunity_version=1,intelligence_id='I1',account_id='PAPER-PRIMARY',symbol='TPR',direction='BULLISH',strategy='LONG_CALL',state='PAPER_READY',version=2,capital=1_000_000,risk_budget_pct=5,risk_budget_amount=50_000,estimated_debit=4.2,estimated_credit=0,max_loss=420,max_profit=None,reward_risk_ratio=None,net_greeks_json={},validation_json={'valid':True},legs_json=_leg(),execution_intent_json={'dynamic_management':mg},notes='',created_by='test',created_at=TS,updated_at=TS))
        s.add(ExecutionIntentModel(execution_intent_id='XI1',trade_plan_id='TP1',trade_plan_version=2,execution_attempt=1,parent_execution_intent_id=None,retry_reason=None,opportunity_id='OP1',portfolio_id='PAPER-PRIMARY',account_id='PAPER-PRIMARY',symbol='TPR',strategy='LONG_CALL',state=state,version=4,max_loss=420,legs_json=_leg(),order_request_json={},validation_json={'valid':True},broker_json={},metadata_json={'dynamic_management':mg},created_by='test',created_at=TS,updated_at=TS2,submitted_at=TS,terminal_at=TS2))
        s.add(BrokerOrderModel(broker_order_record_id='BOR1',binding_id='B1',portfolio_id='PAPER-PRIMARY',aggregate_id='M59-XI1',client_order_id='M59-CLIENT-XI1',broker_account_id='DU123',broker_order_id=61,permanent_id=9001,api_client_id=50,symbol='TPR',security_type='OPT',side='BUY',quantity=1,order_type='LMT',time_in_force='DAY',limit_price=4.0,stop_price=None,status=order_status,filled_quantity=1 if order_status=='FILLED' else 0,remaining_quantity=0 if order_status=='FILLED' else 1,average_fill_price=3.95 if order_status=='FILLED' else 0,submitted_at=TS,updated_at=TS2,last_error='',raw_json={'request':{'metadata':{'execution_intent_id':'XI1'}}}))
        s.add(BrokerPositionSnapshotModel(snapshot_position_id='SP1',account_snapshot_id='S1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',contract_id=817340127,symbol='TPR',local_symbol='TPR   260918C00160000',security_type='OPT',currency='USD',exchange='SMART',quantity=1,average_cost=395.0,expiry='20260918',strike=160.0,right='C',multiplier=100,captured_at=TS2,raw_json={}))
        s.add(BrokerCurrentPositionModel(broker_position_id='BCP1',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU123',account_snapshot_id='S1',contract_id=817340127,symbol='TPR',local_symbol='TPR   260918C00160000',security_type='OPT',currency='USD',exchange='SMART',signed_quantity=1,average_cost=3.95,market_price=3.95,market_value=395,unrealized_pnl=0,realized_pnl=0,expiry='20260918',strike=160.0,right='C',multiplier=100,active=True,provenance='BROKER_DISCOVERED',reconciliation_status='BROKER_DISCOVERED',portfolio_position_id=None,managed_position_id=None,first_seen_at=TS2,last_seen_at=TS2,closed_at=None,raw_json={}))
        s.commit()


def _recover(s):
    snaps=list(s.scalars(select(BrokerPositionSnapshotModel)).all())
    current=list(s.scalars(select(BrokerCurrentPositionModel)).all())
    return BrokerPortfolioSynchronizationService._recover_platform_intent_lineages(s,'PAPER-PRIMARY',snaps,current),current


def test_filled_platform_order_overrides_cancelled_intent_and_establishes_ownership(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='CANCELLED',order_status='FILLED')
    with Session() as s:
        recovered,current=_recover(s)
        assert set(recovered)=={817340127}
        lineage=recovered[817340127]
        assert lineage['position_ownership']['origin']=='PLATFORM'
        assert lineage['position_ownership']['authority']=='BROKER_ORDER_FILLED_EXACT_LINEAGE'
        assert lineage['position_ownership']['broker_order_id']==61
        intent=s.get(ExecutionIntentModel,'XI1')
        assert intent.state=='FILLED'
        audit=s.scalar(select(ExecutionIntentAuditModel).where(ExecutionIntentAuditModel.execution_intent_id=='XI1'))
        assert audit.event_type=='BROKER_TRUTH_PLATFORM_OWNERSHIP_RECONCILED'
        assert audit.previous_state=='CANCELLED' and audit.new_state=='FILLED'

        row=current[0];row.provenance='INSTITUTIONAL_OPTIONS';row.reconciliation_status='MATCHED'
        managed=BrokerPortfolioSynchronizationService._upsert_managed_position(s,row,lineage,'test')
        row.managed_position_id=managed.position_id
        s.commit()
        assert managed.metadata_json['position_ownership']['origin']=='PLATFORM'
        assert managed.metadata_json['position_ownership']['bootstrap_state']=='AUTO_BOOTSTRAPPING'

        result=AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test')
        assert result['positions_armed']==1
        s.refresh(managed)
        assert managed.metadata_json['position_ownership']['bootstrap_state']=='AUTO_MANAGED'
        exits=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==managed.position_id)).all())
        assert exits and any(x.status=='ARMED' for x in exits)


def test_cancelled_intent_without_broker_fill_does_not_become_platform_owned(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='CANCELLED',order_status='CANCELLED')
    with Session() as s:
        recovered,_=_recover(s)
        assert recovered=={}
        assert s.get(ExecutionIntentModel,'XI1').state=='CANCELLED'


def test_entry_manager_detects_filled_platform_order_missing_managed_position(tmp_path):
    Session=_Session(tmp_path);_seed(Session,state='CANCELLED',order_status='FILLED')
    with Session() as s:
        mgr=AutomaticEntryFillManager(s)
        pending=mgr._platform_fills_needing_bootstrap('PAPER-PRIMARY')
        assert [x.broker_order_record_id for x in pending]==['BOR1']
        recovered,current=_recover(s)
        row=current[0];row.provenance='INSTITUTIONAL_OPTIONS';row.reconciliation_status='MATCHED'
        managed=BrokerPortfolioSynchronizationService._upsert_managed_position(s,row,recovered[row.contract_id],'test')
        row.managed_position_id=managed.position_id;s.commit()
        assert mgr._platform_fills_needing_bootstrap('PAPER-PRIMARY')==[]
