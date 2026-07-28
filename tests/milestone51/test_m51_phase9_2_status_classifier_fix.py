from trading_ai.paper_trading.operational_readiness import PhaseStatusRegistry


def test_unhealthy_is_warning_not_healthy_pass():
    result = PhaseStatusRegistry().classify(
        7, "PHASE7_AUTOMATION_UNHEALTHY"
    )
    assert result.disposition == "WARN"
    assert result.reason == "CONTROLLED_NON_TERMINAL_OR_ATTENTION_STATE"


def test_healthy_remains_pass():
    result = PhaseStatusRegistry().classify(
        7, "PHASE7_AUTOMATION_HEALTHY"
    )
    assert result.disposition == "PASS"


def test_failed_remains_fail():
    result = PhaseStatusRegistry().classify(
        7, "PHASE7_AUTOMATION_FAILED"
    )
    assert result.disposition == "FAIL"
