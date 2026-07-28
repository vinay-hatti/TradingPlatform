from trading_ai.paper_trading.automation_control_plane import (
    AutomationControlPlaneService,
    render_control_plane_markdown,
)


def reports():
    return {
        1: {
            "status": "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED",
            "handoff_succeeded": 1,
            "handoff_rejected": 0,
        },
        2: {
            "status": "PHASE2_LIFECYCLE_SYNCHRONIZED",
            "summary": {
                "active_orders": 0,
                "terminal_orders": 1,
                "execution_count": 1,
                "stale_orders": 0,
            },
        },
        3: {
            "status": "PHASE3_POSITIONS_MONITORED",
            "total_positions": 1,
            "exit_candidates": 0,
            "submitted_exits": 0,
        },
        4: {
            "status": "PHASE4_PORTFOLIO_HEALTHY",
            "health": {"overall": 95, "grade": "A"},
            "risk_breaches": [],
            "recommendations": [],
            "state": {
                "net_liquidation_value": 100000,
                "daily_pnl": 500,
            },
        },
    }


def test_cycle_is_ready_and_reportable():
    result = AutomationControlPlaneService().execute(
        "PAPER-PRIMARY", reports(), mode="DRY_RUN"
    )
    assert result.status == "PHASE5_AUTOMATION_READY"
    assert result.consolidated_summary["phase4"]["health_score"] == 95
    markdown = render_control_plane_markdown(result.to_dict())
    assert "Automation Control Plane" in markdown
    assert "Net liquidation value" in markdown
