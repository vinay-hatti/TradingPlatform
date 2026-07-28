from datetime import datetime, timezone

from trading_ai.paper_trading.automation_scheduler import (
    AutomationSchedulerEngine,
    AutomationSchedulerPolicy,
)


NOW = datetime(2026, 7, 27, 14, 0, tzinfo=timezone.utc)


def test_dry_run_is_allowed():
    decision = AutomationSchedulerEngine().authorize(
        "PAPER-PRIMARY",
        "DAILY",
        "2026-07-27-AM",
        mode="DRY_RUN",
        now=NOW,
    )
    assert decision.allowed is True


def test_duplicate_run_is_blocked():
    decision = AutomationSchedulerEngine().authorize(
        "PAPER-PRIMARY",
        "DAILY",
        "2026-07-27-AM",
        mode="DRY_RUN",
        existing_run_keys=["2026-07-27-AM"],
        now=NOW,
    )
    assert decision.allowed is False
    assert "DUPLICATE_RUN_KEY" in decision.reason_codes


def test_submit_requires_exact_confirmation():
    engine = AutomationSchedulerEngine()
    denied = engine.authorize(
        "PAPER-PRIMARY",
        "DAILY",
        "2026-07-27-AM",
        mode="SUBMIT",
        now=NOW,
    )
    assert denied.allowed is False
    allowed = engine.authorize(
        "PAPER-PRIMARY",
        "DAILY",
        "2026-07-27-AM",
        mode="SUBMIT",
        confirmation=(
            "RUN SCHEDULED PAPER AUTOMATION "
            "PAPER-PRIMARY 2026-07-27-AM"
        ),
        now=NOW,
    )
    assert allowed.allowed is True


def test_kill_switch_blocks_run():
    engine = AutomationSchedulerEngine(
        AutomationSchedulerPolicy(kill_switch_active=True)
    )
    decision = engine.authorize(
        "PAPER-PRIMARY",
        "DAILY",
        "2026-07-27-AM",
        mode="DRY_RUN",
        now=NOW,
    )
    assert decision.allowed is False
    assert "KILL_SWITCH_ACTIVE" in decision.reason_codes
