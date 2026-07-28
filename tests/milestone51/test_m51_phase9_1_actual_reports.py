from trading_ai.paper_trading.operational_readiness import (
    DependencyValidator,
    GovernanceValidator,
)


def test_actual_phase_statuses_do_not_create_false_failures():
    reports = {
        1: {"status": "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED"},
        2: {"status": "PHASE2_LIFECYCLE_SYNCHRONIZED"},
        3: {"status": "NO_OPEN_POSITIONS"},
        4: {"status": "PHASE4_NO_OPEN_POSITIONS"},
        5: {
            "status": "PHASE5_AUTOMATION_READY_WITH_WARNINGS",
            "metadata": {"live_trading_enabled": False, "paper_only": True},
            "decision": {"kill_switch_active": False},
        },
        6: {
            "status": "PHASE6_SCHEDULED_RUN_BLOCKED",
            "metadata": {
                "live_trading_enabled": False,
                "duplicate_run_prevention": True,
                "restart_safe": True,
            },
        },
        7: {"overall_status": "PHASE7_AUTOMATION_UNHEALTHY"},
        8: {
            "status": "PHASE8_RECOVERY_BLOCKED",
            "authorization": {"kill_switch_active": False},
        },
    }
    dependency = DependencyValidator().validate(reports, tuple(range(1, 9)))
    assert all(row.status != "FAIL" for row in dependency)

    governance = GovernanceValidator().validate(reports)
    assert all(row.status != "FAIL" for row in governance)
    recovery = next(row for row in governance if row.control_id == "GOV-RECOVERY")
    assert recovery.status == "WARN"
