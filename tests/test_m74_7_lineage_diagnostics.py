from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.broker_portfolio_sync.lineage_diagnostics import LineageDiagnosticsService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TS='2026-08-11T16:55:00+00:00'; TS2='2026-08-11T17:00:00+00:00'

def Session(tmp_path):
    e=create_engine(f"sqlite+pysqlite:///{tmp_path/'m747.db'}");Base.metadata.create_all(e);return sessionmaker(e,expire_on_commit=False)

def legs(): return [
 {'side':'BUY','quantity':1,'option_right':'CALL','strike':28.0,'expiry':'2026-09-18','option_symbol':'O:CCL260918C00028000'},
 {'side':'SELL','quantity':1,'option_right':'CALL','strike':30.0,'expiry':'2026-09-18','option_symbol':'O:CCL260918C00030000'}]

def seed_plan(s,tp='TP1',xi='XI1'):
    mg={'underlying_stop':26.9,'underlying_targets':[29,30,31],'emergency_option_stop_pct':.55}
    s.add(TradePlanModel(trade_plan_id=tp,opportunity_id='OP'+tp,opportunity_version=1,intelligence_id='I',account_id='PAPER-PRIMARY',symbol='CCL',direction='BULLISH',strategy='BULL_CALL_SPREAD',state='PAPER_READY',version=1,capital=1e6,risk_budget_pct=5,risk_budget_amount=50000,estimated_debit=1.03,estimated_credit=0,max_loss=103,max_profit=97,reward_risk_ratio=.94,net_greeks_json={},validation_json={'valid':True},legs_json=legs(),execution_intent_json={'dynamic_management':mg},notes='',created_by='t',created_at=TS,updated_at=TS))
    s.add(ExecutionIntentModel(execution_intent_id=xi,trade_plan_id=tp,trade_plan_version=1,execution_attempt=1,parent_execution_intent_id=None,retry_reason=None,opportunity_id='OP'+tp,portfolio_id='PAPER-PRIMARY',account_id='PAPER-PRIMARY',symbol='CCL',strategy='BULL_CALL_SPREAD',state='APPROVED',version=1,max_loss=103,legs_json=legs(),order_request_json={},validation_json={'valid':True},broker_json={},metadata_json={},created_by='t',created_at=TS,updated_at=TS,submitted_at=None,terminal_at=None))

def seed_broker(s, include_short=True):
    rows=[(853145511,'CCL   260918C00028000',1,28.0)]
    if include_short: rows.append((786955447,'CCL   260918C00030000',-1,30.0))
    for cid,local,qty,strike in rows:
        s.add(BrokerCurrentPositionModel(broker_position_id=f'B{cid}',portfolio_id='PAPER-PRIMARY',binding_id='B1',broker_account_id='DU1',account_snapshot_id='S1',contract_id=cid,symbol='CCL',local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',signed_quantity=qty,average_cost=1,market_price=1,market_value=100,unrealized_pnl=0,realized_pnl=0,expiry='20260918',strike=strike,right='C',multiplier=100,active=True,provenance='BROKER_DISCOVERED',reconciliation_status='BROKER_DISCOVERED',portfolio_position_id=None,managed_position_id=None,first_seen_at=TS2,last_seen_at=TS2,closed_at=None,raw_json={}))

def test_exact_full_leg_set_without_broker_order_is_explained_as_auto_recoverable(tmp_path):
    S=Session(tmp_path)
    with S() as s:
        seed_plan(s);seed_broker(s);s.commit();out=LineageDiagnosticsService(s).diagnose()
        assert out['summary']['AUTO_RECOVERABLE']==1
        row=out['positions'][0];assert row['best_candidate']['execution_intent_id']=='XI1'
        assert row['best_candidate']['evidence']['complete_leg_set'] is True
        assert 'BROKER_ORDER_LINEAGE_MISSING' in row['blockers']
        assert row['confidence']>=85

def test_partial_leg_set_is_not_auto_recoverable(tmp_path):
    S=Session(tmp_path)
    with S() as s:
        seed_plan(s);seed_broker(s,include_short=False);s.commit();out=LineageDiagnosticsService(s).diagnose()
        row=out['positions'][0];assert row['recovery_classification']!='AUTO_RECOVERABLE'
        assert 'INCOMPLETE_LEG_SET' in row['blockers']

def test_ambiguous_full_leg_candidates_are_blocked(tmp_path):
    S=Session(tmp_path)
    with S() as s:
        seed_plan(s,'TP1','XI1');seed_plan(s,'TP2','XI2');seed_broker(s);s.commit();out=LineageDiagnosticsService(s).diagnose()
        row=out['positions'][0];assert row['recovery_classification']=='BLOCKED_REVIEW'
        assert 'AMBIGUOUS_HIGH_CONFIDENCE_CANDIDATES' in row['blockers']

def test_recovered_position_reports_protection_consistency(tmp_path):
    S=Session(tmp_path)
    with S() as s:
        seed_plan(s);seed_broker(s)
        m=ManagedPositionModel(position_id='POS1',portfolio_id='PAPER-PRIMARY',trade_plan_id='TP1',opportunity_id='OPTP1',intelligence_id='I',execution_id='XI1',symbol='CCL',strategy='BULL_CALL_SPREAD',direction='BULLISH',state='OPEN',version=1,opened_at=TS2,closed_at=None,entry_value=103,realized_pnl=0,mark_json={'quantity':1},health_json={},decision_json={},metadata_json={'broker_discovered':False,'automation_mode':'FULLY_AUTOMATIC'},created_by='t',created_at=TS2,updated_at=TS2);s.add(m)
        for b in s.query(BrokerCurrentPositionModel).all(): b.managed_position_id='POS1';b.provenance='INSTITUTIONAL_OPTIONS'
        s.add(M73PositionManagerModel(manager_id='MGR1',position_id='POS1',portfolio_id='PAPER-PRIMARY',state='ACTIVE',automation_mode='FULLY_AUTOMATIC',protection_state='UNPROTECTED',heartbeat_at=TS2,activated_at=TS2,recovered_at=None,last_decision='HOLD',conviction_score=50,thesis_integrity=.5,metadata_json={}))
        s.add(PositionExitInstructionModel(instruction_id='E1',assessment_id='A1',position_id='POS1',action='CLOSE',quantity=1,status='ARMED',payload={'label':'STRUCTURAL_STOP'},created_at=TS2));s.commit()
        out=LineageDiagnosticsService(s).diagnose();row=out['positions'][0]
        assert row['recovery_classification']=='RECOVERED'
        assert row['management']['protection_consistency']=='STALE_PROTECTION_STATE'
