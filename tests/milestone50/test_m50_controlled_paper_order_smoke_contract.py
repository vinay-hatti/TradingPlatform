from pathlib import Path

SCRIPT = Path("scripts/run_m50_controlled_ibkr_paper_order_smoke_test.py")


def test_smoke_runner_exists_and_has_hard_guards():
    text = SCRIPT.read_text()
    assert "RUN IBKR PAPER ORDER SMOKE TEST" in text
    assert "paper_order_submission_enabled" in text
    assert 'environment"] != "PAPER"' in text
    assert "live_trading_enabled" in text
    assert "startswith(\"DU\")" in text
    assert 'order_type="LMT"' in text
    assert "idempotent replay protection failed" in text
    assert "service.cancel" in text
    assert "transport.disconnect" in text
