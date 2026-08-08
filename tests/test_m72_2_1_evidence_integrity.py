from pathlib import Path
from types import SimpleNamespace
from trading_ai.performance_learning.outcome_engine import _select_lifecycle_outcome
from trading_ai.performance_learning import continuous_learning as cl

ROOT=Path(__file__).resolve().parents[1]

def test_m7221_version():
    assert cl.VERSION.startswith('M72.2.1-')

def test_lifecycle_selector_reuses_exact_or_latest_record():
    rows=[SimpleNamespace(position_version=10),SimpleNamespace(position_version=20),SimpleNamespace(position_version=30)]
    assert _select_lifecycle_outcome(rows,20).position_version==20
    assert _select_lifecycle_outcome(rows,31).position_version==30
    assert _select_lifecycle_outcome([],31) is None

def test_reconstruction_queries_by_position_identity_not_position_version():
    source=(ROOT/'src/trading_ai/performance_learning/outcome_engine.py').read_text()
    assert 'TradeOutcomeModel.position_id==p.position_id).order_by(TradeOutcomeModel.position_version.desc())' in source
    assert 'TradeOutcomeModel.position_id==p.position_id,TradeOutcomeModel.position_version==p.version' not in source
    assert 'existing=_select_lifecycle_outcome(existing_rows,p.version)' in source

def test_repair_is_dry_run_by_default_and_audited_on_apply():
    source=(ROOT/'scripts/repair_m72_2_1_trade_outcome_duplicates.py').read_text()
    assert "ap.add_argument('--apply',action='store_true'" in source
    assert "SAFE_SYNTHETIC_OPEN_DUPLICATES" in source
    assert "MANUAL_REVIEW_REQUIRED" in source
    assert "TRADE_OUTCOME_DUPLICATE_CONSOLIDATION" in source
    assert 'LearningAuditEventModel' in source

def test_execution_diagnostic_distinguishes_no_fills_from_incomplete_history():
    source=(ROOT/'scripts/diagnose_m72_evidence_pipeline.py').read_text()
    for token in ('NO_FILLS_AVAILABLE','EXECUTION_HISTORY_INCOMPLETE','never_routed_intents','routed_without_telemetry','filled_broker_orders'):
        assert token in source
    service=Path(cl.__file__).read_text()
    for token in ('broker_execution_sync_state','NO_FILLS_AVAILABLE','EXECUTION_HISTORY_INCOMPLETE','not_routed_intents','routed_without_persisted_order'):
        assert token in service

def test_ui_surfaces_evidence_integrity_states():
    ui=(ROOT/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
    for token in ('M72.2.1','Never routed intents','Filled broker orders','Execution sync state','NO_FILLS_AVAILABLE','Routed without telemetry'):
        assert token in ui

def test_reconstruct_outcomes_is_idempotent_across_operational_version_churn():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PositionEventModel
    from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel
    from trading_ai.portfolio_risk_allocation.models import PortfolioDecisionIntelligenceModel
    from trading_ai.performance_learning.models import TradeOutcomeModel
    from trading_ai.performance_learning.outcome_engine import Milestone65LearningService

    engine=create_engine('sqlite+pysqlite:///:memory:')
    for table in (ManagedPositionModel.__table__,PositionEventModel.__table__,InstitutionalDecisionSnapshotModel.__table__,PortfolioDecisionIntelligenceModel.__table__,TradeOutcomeModel.__table__):
        table.create(engine,checkfirst=True)
    with Session(engine) as s:
        p=ManagedPositionModel(position_id='P1',portfolio_id='PAPER-PRIMARY',trade_plan_id='TP1',opportunity_id='OP1',intelligence_id=None,execution_id=None,symbol='TEST',strategy='LONG_CALL',direction='BULLISH',state='OPEN',version=10,opened_at='2026-08-01T12:00:00+00:00',closed_at=None,entry_value=100.0,realized_pnl=0.0,mark_json={'unrealized_pnl':5.0},health_json={'confidence':0.6},decision_json={},metadata_json={},created_by='test',created_at='2026-08-01T12:00:00+00:00',updated_at='2026-08-08T12:00:00+00:00')
        s.add(p);s.commit()
        r1=Milestone65LearningService(s).reconstruct_outcomes('PAPER-PRIMARY')
        assert r1['created']==1
        p.version=11;p.updated_at='2026-08-08T12:01:00+00:00';s.commit()
        r2=Milestone65LearningService(s).reconstruct_outcomes('PAPER-PRIMARY')
        rows=list(s.scalars(select(TradeOutcomeModel)))
        assert r2['created']==0 and r2['refreshed']==1
        assert len(rows)==1
        assert rows[0].position_version==11
