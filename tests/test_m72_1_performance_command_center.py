from pathlib import Path

from trading_ai.performance_learning import continuous_learning as cl


def test_m721_version_and_governed_threshold_contract():
    assert cl.VERSION.startswith('M72.')
    source = Path(cl.__file__).read_text()
    assert 'REVIEWABLE' in source
    assert 'DEVELOPING' in source
    assert 'INSUFFICIENT_SAMPLE' in source
    assert 'automatic_weight_activation' in source
    assert 'False' in source


def test_m721_dashboard_contract_contains_evidence_center_fields():
    source = Path(cl.__file__).read_text()
    for token in (
        'completion_rate_pct', 'by_source', 'recent_predictions',
        'calibration_bias', 'by_symbol', 'recent_outcomes',
        'evidence_readiness', 'reviewable_segments',
    ):
        assert token in source, token


def test_m721_ui_exposes_command_center_sections():
    root = Path(__file__).resolve().parents[1]
    ui = (root/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
    for token in (
        'Performance Command Center',
        'Prediction registry',
        'Recent prediction → outcome lineage',
        'OPEX forecast validation',
        'Execution quality & edge preservation',
        'M72 segmented calibration health',
        'Evidence readiness',
        'Run learning cycle',
    ):
        assert token in ui, token
