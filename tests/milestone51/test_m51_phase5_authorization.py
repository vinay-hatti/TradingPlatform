from trading_ai.paper_trading.automation_control_plane import (
    AutomationControlPlaneEngine,
    AutomationControlPlanePolicy,
)


def phase4(health=90, breaches=None):
    return {
        "health": {"overall": health},
        "risk_breaches": breaches or [],
    }


def test_dry_run_is_allowed_without_confirmation():
    decision = AutomationControlPlaneEngine().authorize(
        "PAPER-PRIMARY", "DRY_RUN", phase4_report=phase4()
    )
    assert decision.allowed is True


def test_submit_requires_exact_confirmation():
    engine = AutomationControlPlaneEngine()
    denied = engine.authorize(
        "PAPER-PRIMARY", "SUBMIT", phase4_report=phase4()
    )
    assert denied.allowed is False
    assert "CONFIRMATION_MISMATCH" in denied.reason_codes
    allowed = engine.authorize(
        "PAPER-PRIMARY",
        "SUBMIT",
        confirmation="RUN AUTOMATED PAPER TRADING CYCLE PAPER-PRIMARY",
        phase4_report=phase4(),
    )
    assert allowed.allowed is True


def test_risk_breach_blocks_submission():
    decision = AutomationControlPlaneEngine().authorize(
        "PAPER-PRIMARY",
        "SUBMIT",
        confirmation="RUN AUTOMATED PAPER TRADING CYCLE PAPER-PRIMARY",
        phase4_report=phase4(
            breaches=[{"code": "SECTOR_CONCENTRATION"}]
        ),
    )
    assert decision.allowed is False
    assert "PORTFOLIO_RISK_BREACH_ACTIVE" in decision.reason_codes


def test_kill_switch_blocks_submission():
    engine = AutomationControlPlaneEngine(
        AutomationControlPlanePolicy(kill_switch_active=True)
    )
    decision = engine.authorize(
        "PAPER-PRIMARY",
        "SUBMIT",
        confirmation="RUN AUTOMATED PAPER TRADING CYCLE PAPER-PRIMARY",
        phase4_report=phase4(),
    )
    assert decision.allowed is False
    assert "KILL_SWITCH_ACTIVE" in decision.reason_codes
