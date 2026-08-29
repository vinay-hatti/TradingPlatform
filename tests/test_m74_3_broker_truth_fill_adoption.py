from __future__ import annotations
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.database.base import Base
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TS='2026-08-11T14:00:00+00:00'

def _session(tmp_path):
    engine=create_engine(f"sqlite+pysqlite:///{tmp_path/'m743.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)

def _seed(Session,qty=2):
    mg={'underlying_stop':50.0,'underlying_targets':[55.0,57.0,60.0],'theta_exit_days_to_expiry':5,'volatility_exit_rule':'EXIT_ON_IV_COLLAPSE','emergency_option_stop_pct':0.55,'partial_profit_fraction':0.33}
    with Session() as s:
        s.add(TradePlanModel(trade_plan_id='TP1',opportunity_id='OP1',opportunity_version=1,intelligence_id=None,account_id='PAPER-PRIMARY',symbol='CCL',direction='BULLISH',strategy='BULL_CALL_SPREAD',state='PAPER_READY',version=1,capital=10000,risk_budget_pct=1,risk_budget_amount=100,estimated_debit=1.0,estimated_credit=0,max_loss=100,max_profit=100,reward_risk_ratio=1,net_greeks_json={},validation_json={},legs_json=[],execution_intent_json={'dynamic_management':mg},notes='',created_by='test',created_at=TS,updated_at=TS))
        s.add(ManagedPositionModel(position_id='POS1',portfolio_id='PAPER-PRIMARY',trade_plan_id='TP1',opportunity_id='OP1',intelligence_id=None,execution_id='XI1',symbol='CCL',strategy='BULL_CALL_SPREAD',direction='BULLISH',state='OPEN',version=1,opened_at=TS,closed_at=None,entry_value=100,realized_pnl=0,mark_json={'mark_price':1.0,'quantity':qty,'market_value':100*qty,'unrealized_pnl':0,'unrealized_return_pct':0,'delta':0,'gamma':0,'theta':0,'vega':0,'days_to_expiry':30},health_json={},decision_json={},metadata_json={'automation_mode':'FULLY_AUTOMATIC','management_mode':'PLATFORM_MANAGED','dynamic_management':mg},created_by='test',created_at=TS,updated_at=TS))
        s.add(M73PositionManagerModel(manager_id='MGR1',position_id='POS1',portfolio_id='PAPER-PRIMARY',state='ACTIVE',automation_mode='FULLY_AUTOMATIC',protection_state='UNPROTECTED',heartbeat_at=TS,activated_at=TS,recovered_at=None,last_decision='HOLD',conviction_score=50,thesis_integrity=.5,metadata_json={}))
        s.add(BrokerCurrentPositionModel(broker_position_id='BCP1',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU1',account_snapshot_id='S1',contract_id=1,symbol='CCL',local_symbol='CCL   260918C00028000',security_type='OPT',currency='USD',exchange='SMART',signed_quantity=qty,average_cost=1.0,market_price=1.0,market_value=100*qty,unrealized_pnl=0,realized_pnl=0,expiry='20260918',strike=28,right='C',multiplier=100,active=True,provenance='INSTITUTIONAL_OPTIONS',reconciliation_status='MATCHED',portfolio_position_id=None,managed_position_id='POS1',first_seen_at=TS,last_seen_at=TS,closed_at=None,raw_json={}))
        s.add(PositionExitInstructionModel(instruction_id='OLD',assessment_id='OLD',position_id='POS1',action='CLOSE',quantity=0,status='CANCELLED',payload={'label':'STRUCTURAL_STOP','cancel_reason':'NO_REMAINING_BROKER_QUANTITY','management_generation':1},created_at=TS))
        s.commit()

def test_broker_open_quantity_rearms_after_historical_cancelled_generation(tmp_path):
    Session=_session(tmp_path);_seed(Session,qty=2)
    with Session() as s:
        result=AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test')
        assert result['positions_armed']==1
        mgr=s.get(M73PositionManagerModel,'MGR1')
        assert mgr.protection_state=='PLATFORM_PROTECTED'
        assert mgr.metadata_json['fill_adoption_source']=='IBKR_BROKER_TRUTH'
        rows=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id=='POS1')).all())
        active=[x for x in rows if x.status=='ARMED']
        assert active
        assert all((x.payload or {}).get('management_generation')==2 for x in active)
        assert all(0 < int(x.quantity) <= 2 for x in active)
        targets=[x for x in active if str((x.payload or {}).get('label','')).startswith('TARGET_')]
        assert sum(int(x.quantity) for x in targets)<=2

def test_broker_quantity_reduction_resizes_active_instructions_without_overclose(tmp_path):
    Session=_session(tmp_path);_seed(Session,qty=2)
    with Session() as s:
        AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test')
        broker=s.get(BrokerCurrentPositionModel,'BCP1');broker.signed_quantity=1;s.commit()
        AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test2')
        rows=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id=='POS1')).all())
        active=[x for x in rows if x.status=='ARMED']
        assert all(int(x.quantity)<=1 for x in active)
        targets=[x for x in active if str((x.payload or {}).get('label','')).startswith('TARGET_')]
        assert sum(int(x.quantity) for x in targets)<=1

def test_entry_fill_manager_forces_authoritative_portfolio_sync_after_broker_fill():
    src=(Path(__file__).resolve().parents[1]/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
    assert 'fill_adoption_required=True' in src
    assert 'BrokerPortfolioSynchronizationService(SessionLocal).synchronize' in src
    assert "actor='M74_BROKER_TRUTH_FILL_ADOPTION'" in src

def test_execution_workspace_rearms_when_only_historical_exit_instructions_exist():
    src=(Path(__file__).resolve().parents[1]/'src/trading_ai/execution_workspace/service.py').read_text()
    assert "terminal={'FILLED','CANCELLED','CANCELED','REJECTED','FAILED'}" in src
    assert "management_generation" in src
    assert "IBKR_BROKER_TRUTH_FILL_ADOPTION" in src
    assert "mapped in {'PARTIALLY_FILLED','FILLED'}" in src
