from trading_ai.paper_trading.automation_recovery import (
    AutomationRecoveryEngine,
    AutomationRecoveryPolicy,
)


def test_analyze_requires_no_confirmation():
    result = AutomationRecoveryEngine().authorize(
        "PAPER-PRIMARY", "RUN-1", mode="ANALYZE"
    )
    assert result.allowed is True


def test_recover_requires_exact_confirmation():
    engine = AutomationRecoveryEngine()
    denied = engine.authorize("PAPER-PRIMARY", "RUN-1", mode="RECOVER")
    assert denied.allowed is False
    allowed = engine.authorize(
        "PAPER-PRIMARY",
        "RUN-1",
        mode="RECOVER",
        confirmation="RECOVER PAPER AUTOMATION PAPER-PRIMARY RUN-1",
    )
    assert allowed.allowed is True


def test_kill_switch_blocks_recover():
    engine = AutomationRecoveryEngine(
        AutomationRecoveryPolicy(kill_switch_active=True)
    )
    decision = engine.authorize(
        "PAPER-PRIMARY",
        "RUN-1",
        mode="RECOVER",
        confirmation="RECOVER PAPER AUTOMATION PAPER-PRIMARY RUN-1",
    )
    assert decision.allowed is False
    assert "KILL_SWITCH_ACTIVE" in decision.reason_codes
