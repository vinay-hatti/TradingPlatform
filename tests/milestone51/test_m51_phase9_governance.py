from trading_ai.paper_trading.operational_readiness import GovernanceValidator


def test_governance_controls_pass():
    reports = {
        5: {
            "status": "PHASE5_AUTOMATION_READY",
            "metadata": {"live_trading_enabled": False, "paper_only": True},
            "decision": {"kill_switch_active": False},
        },
        6: {
            "status": "PHASE6_SCHEDULED_RUN_COMPLETED",
            "metadata": {
                "live_trading_enabled": False,
                "duplicate_run_prevention": True,
                "restart_safe": True,
            },
        },
        8: {
            "status": "PHASE8_RECOVERY_NOT_REQUIRED",
            "authorization": {"kill_switch_active": False},
        },
    }
    controls = GovernanceValidator().validate(reports)
    assert all(row.status == "PASS" for row in controls)
