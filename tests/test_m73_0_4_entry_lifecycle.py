from pathlib import Path

def test_m7304_tokens_present():
    root=Path(__file__).resolve().parents[1]
    auto=(root/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
    ws=(root/'src/trading_ai/execution_workspace/service.py').read_text()
    assert 'M73.0.' in auto and 'ENTRY' in auto
    assert '_broker_sync_once' in auto
    assert 'service.synchronize(portfolio_id)' in auto
    assert 'reconcile_entry_with_broker_truth' in ws
    assert 'BROKER_TRUTH_ENTRY_STATE_REPAIRED' in ws
    assert 'ORDER_AGE_EXCEEDED' in ws
    assert 'cancel_required' in ws
    assert 'automatic=True' in auto
