from trading_ai.paper_trading.operational_readiness import PhaseStatusRegistry


def test_actual_phase1_and_phase2_statuses_pass():
    registry = PhaseStatusRegistry()
    assert registry.classify(
        1, "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED"
    ).disposition == "PASS"
    assert registry.classify(
        2, "PHASE2_LIFECYCLE_SYNCHRONIZED"
    ).disposition == "PASS"


def test_blocked_status_warns_not_fails():
    registry = PhaseStatusRegistry()
    assert registry.classify(
        6, "PHASE6_SCHEDULED_RUN_BLOCKED"
    ).disposition == "WARN"
    assert registry.classify(
        8, "PHASE8_RECOVERY_BLOCKED"
    ).disposition == "WARN"


def test_explicit_failure_still_fails():
    registry = PhaseStatusRegistry()
    assert registry.classify(
        7, "PHASE7_AUTOMATION_FAILED"
    ).disposition == "FAIL"
