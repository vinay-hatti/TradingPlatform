from pathlib import Path

from trading_ai.institutional_options.decision import InstitutionalDecisionService


def test_decision_snapshot_reads_nested_calibrated_probability():
    source = Path('src/trading_ai/institutional_options/decision.py').read_text()
    assert 'def _calibrated_probability' in source
    assert 'probability.get("calibrated_probability")' in source


def test_targets_are_directionally_ordered_and_labeled():
    assert InstitutionalDecisionService._normalize_targets(
        [94.6998, 80.8133, 82.063], direction='BULLISH', entry_low=80.46, entry_high=80.76
    ) == [80.8133, 82.063, 94.6998]
    assert InstitutionalDecisionService._normalize_targets(
        [90, 80, 85], direction='BEARISH', entry_low=95, entry_high=96
    ) == [90.0, 85.0, 80.0]
    source = Path('src/trading_ai/institutional_options/decision.py').read_text()
    assert '"target_plan"' in source
    assert '"label": f"TARGET_{index}"' in source


def test_portfolio_context_is_explainable_and_optional():
    source = Path('src/trading_ai/institutional_options/decision.py').read_text()
    for text in (
        'portfolio_fit_score', 'capital_utilization_pct',
        'projected_symbol_exposure_pct', 'PORTFOLIO_CONTEXT_UNAVAILABLE',
        'PROJECTED_SYMBOL_CONCENTRATION_ABOVE_10_PCT',
    ):
        assert text in source


def test_institutional_options_ui_surfaces_final_decision_fields():
    page = Path('ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    for text in (
        'Calibrated POP', 'Expected value', 'Capital required',
        'Portfolio fit', 'Execution quality', 'Institutional decision',
    ):
        assert text in page


def test_existing_scanners_remain_parallel_and_unchanged_in_routing():
    app = Path('ui/workstation/src/App.tsx').read_text()
    assert 'scanner: DailyScannerPage' in app
    assert "'option-scanner': OptionScannerPage" in app
    assert "'institutional-options': InstitutionalOptionsPage" in app


def test_decision_refresh_skips_prerequisites_for_ready_opportunities():
    source = Path('src/trading_ai/institutional_options/decision.py').read_text()
    assert 'OpportunityState.CONTRACTS_OPTIMIZED.value' in source
    assert 'prerequisite_ids' in source
    assert 'with self.session.begin_nested()' in source
    assert 'portfolio context must never block a decision refresh' in source


def test_recovered_prerequisite_errors_are_not_reported_as_terminal_decision_errors():
    source = Path('src/trading_ai/institutional_options/decision.py').read_text()
    assert 'errors: list[str] = []' in source
    assert 'errors: list[str] = list(prerequisite_errors)' not in source
    assert 'Only terminal snapshot' in source
