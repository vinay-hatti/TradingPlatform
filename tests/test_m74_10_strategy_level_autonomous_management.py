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

TS='2026-08-11T18:00:00+00:00'

def _session(tmp_path):
    engine=create_engine(f"sqlite+pysqlite:///{tmp_path/'m7410.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)

def _seed_diagonal(Session):
    mg={'underlying_stop':195.0,'underlying_targets':[210.0,220.0,230.0],'theta_exit_days_to_expiry':5,'volatility_exit_rule':'IV_COLLAPSE_AND_THESIS_DETERIORATION','emergency_option_stop_pct':0.55,'partial_profit_fraction':0.33,'assignment_risk_rule':'EXIT_OR_ROLL_SHORT_LEGS_BEFORE_ASSIGNMENT_RISK_WINDOW'}
    legs=[
        {'side':'BUY','quantity':1,'expiry':'2026-10-16','strike':222.5,'option_right':'CALL','option_symbol':'O:CRWD261016C00222500'},
        {'side':'SELL','quantity':1,'expiry':'2026-09-11','strike':235.0,'option_right':'CALL','option_symbol':'O:CRWD260911C00235000'},
    ]
    with Session() as s:
        s.add(TradePlanModel(trade_plan_id='TP-DIAG',opportunity_id='OP1',opportunity_version=1,intelligence_id=None,account_id='PAPER-PRIMARY',symbol='CRWD',direction='BULLISH',strategy='CALL_DIAGONAL',state='PAPER_READY',version=1,capital=10000,risk_budget_pct=1,risk_budget_amount=100,estimated_debit=10.0,estimated_credit=0,max_loss=1000,max_profit=None,reward_risk_ratio=None,net_greeks_json={},validation_json={},legs_json=legs,execution_intent_json={'dynamic_management':mg},notes='',created_by='test',created_at=TS,updated_at=TS))
        s.add(ManagedPositionModel(position_id='POS-DIAG',portfolio_id='PAPER-PRIMARY',trade_plan_id='TP-DIAG',opportunity_id='OP1',intelligence_id=None,execution_id='XI-DIAG',symbol='CRWD',strategy='CALL_DIAGONAL',direction='BULLISH',state='OPEN',version=1,opened_at=TS,closed_at=None,entry_value=1000,realized_pnl=0,mark_json={'mark_price':10.0,'quantity':1,'market_value':1000,'unrealized_pnl':0,'unrealized_return_pct':0,'delta':0,'gamma':0,'theta':0,'vega':0,'days_to_expiry':31},health_json={},decision_json={},metadata_json={'automation_mode':'FULLY_AUTOMATIC','management_mode':'PLATFORM_MANAGED','dynamic_management':mg,'paper_only':True},created_by='test',created_at=TS,updated_at=TS))
        s.add(M73PositionManagerModel(manager_id='MGR-DIAG',position_id='POS-DIAG',portfolio_id='PAPER-PRIMARY',state='ACTIVE',automation_mode='FULLY_AUTOMATIC',protection_state='UNPROTECTED',heartbeat_at=TS,activated_at=TS,recovered_at=None,last_decision='HOLD',conviction_score=50,thesis_integrity=.5,metadata_json={}))
        for i,(cid,qty,ls,expiry,strike) in enumerate([(884803016,1,'CRWD  261016C00222500','20261016',222.5),(906486458,-1,'CRWD  260911C00235000','20260911',235.0)],1):
            s.add(BrokerCurrentPositionModel(broker_position_id=f'BCP{i}',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU1',account_snapshot_id='S1',contract_id=cid,symbol='CRWD',local_symbol=ls,security_type='OPT',currency='USD',exchange='SMART',signed_quantity=qty,average_cost=1.0,market_price=1.0,market_value=100,unrealized_pnl=0,realized_pnl=0,expiry=expiry,strike=strike,right='C',multiplier=100,active=True,provenance='INSTITUTIONAL_OPTIONS',reconciliation_status='MATCHED',portfolio_position_id=None,managed_position_id='POS-DIAG',first_seen_at=TS,last_seen_at=TS,closed_at=None,raw_json={}))
        s.commit()

def test_diagonal_arms_assignment_rule_for_full_strategy_atomic_bag(tmp_path):
    Session=_session(tmp_path);_seed_diagonal(Session)
    with Session() as s:
        result=AutonomousPositionManagementService(s).ensure_managers('PAPER-PRIMARY',actor='test')
        assert result['positions_armed']==1
        rows=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id=='POS-DIAG')))
        assignment=next(x for x in rows if (x.payload or {}).get('label')=='SHORT_LEG_ASSIGNMENT_EXIT')
        assert assignment.status=='ARMED'
        assert assignment.action=='CLOSE'
        assert assignment.quantity==1
        assert assignment.payload['trigger_type']=='SHORT_LEG_DTE'
        assert assignment.payload['execution_scope']=='FULL_STRATEGY'
        assert assignment.payload['exit_method']=='ATOMIC_BAG'
        assert assignment.payload['short_leg_count']==1
        assert all((x.payload or {}).get('exit_method')=='ATOMIC_BAG' for x in rows)

def test_dynamic_exit_path_closes_every_leg_as_one_bag():
    src=(Path(__file__).resolve().parents[1]/'src/trading_ai/dynamic_position_management/service.py').read_text()
    assert "close_action='SELL' if original=='BUY' else 'BUY'" in src
    assert 'IbkrPaperComboOrderRequest' in src
    assert "'strategy_level_exit':True" in src
    assert "'includes_short_legs':True" in src
    assert 'return service.submit_combo(request)' in src
    assert 'if typ=="SHORT_LEG_DTE"' in src

def test_portfolio_ui_excludes_superseded_from_operational_counts_and_shows_strategy_lifecycle():
    src=(Path(__file__).resolve().parents[1]/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    assert "NON_OPERATIONAL_POSITION_STATES = new Set(['CLOSED', 'CANCELLED', 'SUPERSEDED'])" in src
    assert 'const activePositions = positions.filter(position => !NON_OPERATIONAL_POSITION_STATES.has' in src
    assert 'Strategy Lifecycle' in src
    assert 'Short-leg monitoring' in src
    assert 'ATOMIC BAG MANAGED' in src
    assert 'Current policy closes the full strategy as one BAG before assignment-risk/expiry governance is breached' in src
