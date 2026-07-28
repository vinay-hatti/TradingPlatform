from pathlib import Path

from trading_ai.paper_trading.operational_readiness import (
    OperationalReadinessService,
    render_readiness_html,
    render_readiness_markdown,
)


def test_full_readiness_and_reporting(tmp_path):
    (tmp_path / "src/trading_ai").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")

    reports = {
        1: {"status": "PHASE1_AUTOMATION_READY"},
        2: {"status": "NO_ACTIVE_ORDERS"},
        3: {"status": "NO_OPEN_POSITIONS"},
        4: {"status": "PHASE4_PORTFOLIO_HEALTHY"},
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
        7: {"overall_status": "PHASE7_AUTOMATION_HEALTHY"},
        8: {
            "status": "PHASE8_RECOVERY_NOT_REQUIRED",
            "authorization": {"kill_switch_active": False},
        },
    }
    result = OperationalReadinessService().execute(
        "PAPER-PRIMARY", reports, repo_root=tmp_path, mode="FULL"
    )
    assert result.overall_status in {
        "PHASE9_OPERATIONALLY_READY",
        "PHASE9_READY_WITH_CONDITIONS",
    }
    assert "Operational Readiness" in render_readiness_markdown(result.to_dict())
    assert "<html>" in render_readiness_html(result.to_dict())
