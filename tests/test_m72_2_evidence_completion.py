from pathlib import Path

from trading_ai.performance_learning import continuous_learning as cl


ROOT = Path(__file__).resolve().parents[1]


def test_m722_version_and_evidence_bridge_contract():
    assert cl.VERSION.startswith('M72.2')
    source = Path(cl.__file__).read_text()
    for token in (
        'def bridge_trade_outcomes',
        'def backfill_execution_evidence',
        'M72.2_TRADE_OUTCOME_BRIDGE',
        'trade_by_decision',
        'OpexIntelligenceService(SessionLocal).realize_outcomes()',
        'broker_sync_mode',
    ):
        assert token in source, token


def test_m722_learning_cycle_orders_source_evidence_before_calibration():
    source = Path(cl.__file__).read_text()
    positions = {
        'trade': source.index('trade_bridge = self.bridge_trade_outcomes'),
        'execution': source.index('execution_bridge = self.backfill_execution_evidence'),
        'capture': source.index('capture = self.capture_predictions'),
        'realize': source.index('realize = self.realize_outcomes'),
        'calibration': source.index('cal = self.build_calibration'),
    }
    assert positions['trade'] < positions['capture']
    assert positions['execution'] < positions['calibration']
    assert positions['capture'] < positions['realize'] < positions['calibration']


def test_m722_execution_backfill_preserves_preflight_intelligence():
    source = (ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    assert 'Historical/backfill path' in source
    assert 'ExecutionIntelligenceSnapshotModel.execution_intent_id==m.execution_intent_id' in source
    assert "'backfilled':True" in source
    assert 'preflight.execution_confidence' in source


def test_m722_cli_keeps_broker_network_sync_explicit():
    source = (ROOT/'scripts/run_m72_learning_cycle.py').read_text()
    assert "--sync-ibkr" in source
    assert 'if a.sync_ibkr:' in source
    assert 'sync_ibkr_execution_history' in source
    assert 'Explicit, operator-requested IBKR paper synchronization' in source


def test_m722_ui_exposes_evidence_pipeline_health():
    ui = (ROOT/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
    for token in (
        'Evidence pipeline health',
        'Unbridged realized trades',
        'Execution learning samples',
        'needs_ibkr_execution_sync',
        'run_m72_learning_cycle.py --sync-ibkr',
    ):
        assert token in ui, token
