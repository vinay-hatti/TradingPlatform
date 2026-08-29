from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerOrderControlModel,
    BrokerOrderModel,
    BrokerPositionSnapshotModel,
)
from trading_ai.broker.ibkr.order_models import IbkrPaperComboLegRequest, IbkrPaperComboOrderRequest
from trading_ai.broker.ibkr.order_service import IbkrPaperOrderService
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.base import Base
from trading_ai.execution_workspace.models import ExecutionIntentAuditModel, ExecutionIntentModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TS='2026-08-11T16:55:00+00:00'
TS2='2026-08-11T17:00:00+00:00'


def _Session(tmp_path):
    engine=create_engine(f"sqlite+pysqlite:///{tmp_path/'m746.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)


def _legs():
    return [
        {'side':'BUY','quantity':1,'option_right':'CALL','strike':28.0,'expiry':'2026-09-18','option_symbol':'O:CCL260918C00028000'},
        {'side':'SELL','quantity':1,'option_right':'CALL','strike':30.0,'expiry':'2026-09-18','option_symbol':'O:CCL260918C00030000'},
    ]


def _seed_binding_and_canonical(Session):
    with Session() as s:
        s.add(BrokerAccountBindingModel(binding_id='B1',portfolio_id='PAPER-PRIMARY',broker_name='INTERACTIVE_BROKERS',broker_environment='PAPER',broker_account_id='DU123',base_currency='USD',host='127.0.0.1',port=7497,client_id=50,read_only=False,live_trading_enabled=False,status='VERIFIED_PAPER_TRADING',created_at=TS,updated_at=TS,metadata_json={}))
        s.add(BrokerOrderControlModel(portfolio_id='PAPER-PRIMARY',paper_order_submission_enabled=True,activation_token_hash='x',activated_at=TS,activated_by='test',disabled_at=None,disable_reason='',version=1,updated_at=TS,metadata_json={}))
        s.add(CanonicalOrderModel(aggregate_id='AG1',client_order_id='C1',account_id='PAPER-PRIMARY',idempotency_key='I1',order_type='LMT',time_in_force='DAY',state='APPROVED',version=1,total_quantity=1,filled_quantity=0,remaining_quantity=1,average_fill_price=None,limit_price=1.03,stop_price=None,outside_regular_hours=False,strategy_name='BULL_CALL_SPREAD',broker_order_id=None,parent_aggregate_id=None,root_aggregate_id='AG1',replace_count=0,legs_json=_legs(),created_at=TS,updated_at=TS,terminal_at=None,last_event_id=None,metadata_json={}))
        s.commit()


class AtomicFakeTransport:
    def __init__(self, Session):
        self.Session=Session
        self.pretransmit_row_seen=False
        self._ack={'acknowledged':True,'callback':'ORDER_STATUS','status':'PRESUBMITTED','permanent_id':999,'filled_quantity':0.0,'remaining_quantity':1.0,'average_fill_price':0.0,'broker_order_id':101}
        self._validation={}
    def health(self): return {'managed_accounts':('DU123',)}
    def set_order_id_floor(self, x): return x
    def reserve_order_id(self): return 101
    def submit_combo_order_prepared(self, request, *, initial_order_id, before_transmit=None):
        norm={'requested_price':1.03,'normalized_price':1.03,'increment':0.01,'valid':True}
        before_transmit(initial_order_id,norm,1,[])
        # Simulate the exact point immediately before placeOrder(): another DB
        # session must already be able to see durable broker lineage.
        with self.Session() as s:
            row=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id=='AG1'))
            self.pretransmit_row_seen=bool(row and row.status=='SUBMISSION_PENDING' and row.broker_order_id==101)
        self._validation={'security_type':'BAG','aggregate_id':'AG1','limit_price':{**norm,'broker_order_id':101,'candidate_attempts':[]}}
        return 101
    def last_outbound_price_validation(self, _): return self._validation
    def wait_for_order_acknowledgement(self, _): return dict(self._ack)


def test_combo_broker_row_is_durable_before_any_transmission(tmp_path):
    Session=_Session(tmp_path);_seed_binding_and_canonical(Session);transport=AtomicFakeTransport(Session)
    req=IbkrPaperComboOrderRequest(aggregate_id='AG1',client_order_id='C1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',symbol='CCL',quantity=1,combo_legs=(IbkrPaperComboLegRequest(853145511,1,'BUY'),IbkrPaperComboLegRequest(786955447,1,'SELL')),limit_price=1.03)
    result=IbkrPaperOrderService(Session,transport).submit_combo(req)
    assert transport.pretransmit_row_seen is True
    assert result['broker_order_id']==101
    with Session() as s:
        row=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id=='AG1'))
        assert row is not None and row.status=='PRESUBMITTED'
        assert row.raw_json['m74_6_atomic_submission']['durable_before_transmit'] is True
        assert row.raw_json['m74_6_atomic_submission']['candidate_history'][0]['broker_order_id']==101


def _seed_recovery(Session):
    mg={'underlying_stop':26.9,'underlying_targets':[29.0,30.0,31.0],'theta_exit_days_to_expiry':5,'volatility_exit_rule':'EXIT_ON_IV_COLLAPSE','emergency_option_stop_pct':0.55,'partial_profit_fraction':0.33}
    with Session() as s:
        s.add(TradePlanModel(trade_plan_id='TP1',opportunity_id='OP1',opportunity_version=1,intelligence_id='I1',account_id='PAPER-PRIMARY',symbol='CCL',direction='BULLISH',strategy='BULL_CALL_SPREAD',state='PAPER_READY',version=2,capital=1_000_000,risk_budget_pct=5,risk_budget_amount=50_000,estimated_debit=1.03,estimated_credit=0,max_loss=103,max_profit=97,reward_risk_ratio=.94,net_greeks_json={},validation_json={'valid':True},legs_json=_legs(),execution_intent_json={'dynamic_management':mg,'decision_snapshot_id':'D1','decision_state_hash':'H1'},notes='',created_by='test',created_at=TS,updated_at=TS))
        s.add(ExecutionIntentModel(execution_intent_id='XI1',trade_plan_id='TP1',trade_plan_version=2,execution_attempt=1,parent_execution_intent_id=None,retry_reason=None,opportunity_id='OP1',portfolio_id='PAPER-PRIMARY',account_id='PAPER-PRIMARY',symbol='CCL',strategy='BULL_CALL_SPREAD',state='APPROVED',version=2,max_loss=103,legs_json=_legs(),order_request_json={},validation_json={'valid':True},broker_json={},metadata_json={'dynamic_management':mg},created_by='test',created_at=TS,updated_at=TS,submitted_at=None,terminal_at=None))
        for cid,local,qty,strike in [(853145511,'CCL   260918C00028000',1,28.0),(786955447,'CCL   260918C00030000',-1,30.0)]:
            s.add(BrokerPositionSnapshotModel(snapshot_position_id=f'SP{cid}',account_snapshot_id='S1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU123',contract_id=cid,symbol='CCL',local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',quantity=qty,average_cost=100.0,expiry='20260918',strike=strike,right='C',multiplier=100,captured_at=TS2,raw_json={}))
            s.add(BrokerCurrentPositionModel(broker_position_id=f'BCP{cid}',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU123',account_snapshot_id='S1',contract_id=cid,symbol='CCL',local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',signed_quantity=qty,average_cost=1.0,market_price=1.0,market_value=100,unrealized_pnl=0,realized_pnl=0,expiry='20260918',strike=strike,right='C',multiplier=100,active=True,provenance='BROKER_DISCOVERED',reconciliation_status='BROKER_DISCOVERED',portfolio_position_id=None,managed_position_id=None,first_seen_at=TS2,last_seen_at=TS2,closed_at=None,raw_json={}))
        s.commit()


def test_exact_full_leg_set_recovers_approved_bag_into_one_autonomous_position(tmp_path):
    Session=_Session(tmp_path);_seed_recovery(Session)
    with Session() as s:
        snaps=list(s.scalars(select(BrokerPositionSnapshotModel)).all());current=list(s.scalars(select(BrokerCurrentPositionModel)).all())
        recovered=BrokerPortfolioSynchronizationService._recover_platform_intent_lineages(s,'PAPER-PRIMARY',snaps,current)
        assert set(recovered)=={853145511,786955447}
        assert all(x['trade_plan_id']=='TP1' and x['execution_intent_id']=='XI1' for x in recovered.values())
        intent=s.get(ExecutionIntentModel,'XI1');assert intent.state=='FILLED'
        audit=s.scalar(select(ExecutionIntentAuditModel).where(ExecutionIntentAuditModel.execution_intent_id=='XI1'))
        assert audit and audit.event_type=='BROKER_POSITION_LINEAGE_RECOVERED'
        managed_ids=[]
        for row in current:
            row.provenance='INSTITUTIONAL_OPTIONS';row.reconciliation_status='MATCHED'
            m=BrokerPortfolioSynchronizationService._upsert_managed_position(s,row,recovered[row.contract_id],'test')
            row.managed_position_id=m.position_id;managed_ids.append(m.position_id)
        assert len(set(managed_ids))==1
        BrokerPortfolioSynchronizationService._aggregate_institutional_managed_positions(s,'PAPER-PRIMARY')
        s.commit()
        m=s.get(ManagedPositionModel,managed_ids[0])
        assert m.strategy=='BULL_CALL_SPREAD'
        assert m.execution_id=='XI1'
        assert m.metadata_json['automation_mode']=='FULLY_AUTOMATIC'
        assert set(m.metadata_json['broker_contract_ids'])=={853145511,786955447}
        assert m.mark_json['quantity']==1
        result=AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test')
        assert result['positions_armed']==1
        exits=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==m.position_id)).all())
        assert any(x.status=='ARMED' for x in exits)


def test_partial_leg_match_does_not_recover_or_enable_automation(tmp_path):
    Session=_Session(tmp_path);_seed_recovery(Session)
    with Session() as s:
        short=s.get(BrokerPositionSnapshotModel,'SP786955447');s.delete(short)
        short_current=s.get(BrokerCurrentPositionModel,'BCP786955447');s.delete(short_current);s.commit()
        snaps=list(s.scalars(select(BrokerPositionSnapshotModel)).all());current=list(s.scalars(select(BrokerCurrentPositionModel)).all())
        recovered=BrokerPortfolioSynchronizationService._recover_platform_intent_lineages(s,'PAPER-PRIMARY',snaps,current)
        assert recovered=={}
        assert s.get(ExecutionIntentModel,'XI1').state=='APPROVED'


def test_ambiguous_exact_leg_set_across_distinct_trade_plans_stays_unrecovered(tmp_path):
    Session=_Session(tmp_path);_seed_recovery(Session)
    with Session() as s:
        # A second distinct platform plan/intent with the same exact leg set makes
        # broker-position-only recovery ambiguous, so M74.6 must refuse adoption.
        s.add(TradePlanModel(trade_plan_id='TP2',opportunity_id='OP2',opportunity_version=1,intelligence_id='I2',account_id='PAPER-PRIMARY',symbol='CCL',direction='BULLISH',strategy='BULL_CALL_SPREAD',state='PAPER_READY',version=1,capital=1_000_000,risk_budget_pct=5,risk_budget_amount=50_000,estimated_debit=1.03,estimated_credit=0,max_loss=103,max_profit=97,reward_risk_ratio=.94,net_greeks_json={},validation_json={'valid':True},legs_json=_legs(),execution_intent_json={'dynamic_management':{}},notes='',created_by='test',created_at=TS,updated_at=TS))
        s.add(ExecutionIntentModel(execution_intent_id='XI2',trade_plan_id='TP2',trade_plan_version=1,execution_attempt=1,parent_execution_intent_id=None,retry_reason=None,opportunity_id='OP2',portfolio_id='PAPER-PRIMARY',account_id='PAPER-PRIMARY',symbol='CCL',strategy='BULL_CALL_SPREAD',state='APPROVED',version=1,max_loss=103,legs_json=_legs(),order_request_json={},validation_json={'valid':True},broker_json={},metadata_json={},created_by='test',created_at=TS,updated_at=TS,submitted_at=None,terminal_at=None));s.commit()
        snaps=list(s.scalars(select(BrokerPositionSnapshotModel)).all());current=list(s.scalars(select(BrokerCurrentPositionModel)).all())
        assert BrokerPortfolioSynchronizationService._recover_platform_intent_lineages(s,'PAPER-PRIMARY',snaps,current)=={}
        assert s.get(ExecutionIntentModel,'XI1').state=='APPROVED'
        assert s.get(ExecutionIntentModel,'XI2').state=='APPROVED'
