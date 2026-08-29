from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()

def test_skipped_targets_render_label_value_rows():
    for marker in ('Skipped targets','Current underlying:','Exceeded by','Undercut by'):
        assert marker in UI
    assert '<b>{x.label||`Target ${x.original_target_number}`}:</b>' in UI
    assert '<b>Current underlying:</b>' in UI
    assert '<b>{distanceLabel}:</b>' in UI

def test_skipped_targets_include_percentage_context():
    assert 'Math.abs(Number(x.distance)/Number(x.target_value))*100' in UI
    assert 'pct.toFixed(2)' in UI

def test_market_data_freshness_is_split_into_rows():
    assert '<b>Underlying quote age:</b>' in UI
    assert '<b>Option quote age:</b>' in UI
    assert 'Underlying quote age:' in UI and 'Option quote age:' in UI

def test_effective_targets_are_renumbered_and_current_objective_is_visible():
    assert '<b>Effective targets</b>' in UI
    assert '<b>Target {i+1}:</b>' in UI
    assert '<b>Current objective:</b>' in UI
    assert '<b>Distance remaining:</b>' in UI

def test_no_targets_remaining_explains_rebuild():
    for marker in ('No executable profit targets remain.','Highest generated target','Lowest generated target','Recommendation:','Rebuild trade plan.'):
        assert marker in UI

def test_execution_intelligence_has_operator_sections():
    for marker in ('Execution validation','Market data','Directional target validation'):
        assert marker in UI
