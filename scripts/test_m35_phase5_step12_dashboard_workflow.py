from pathlib import Path

from trading_ai.scanner.dashboard.dashboard_workflow_service import (
    DashboardWorkflowService,
)


def main() -> None:
    artifacts = {
        "MARKET_SCAN": (
            Path("market_scan.json"),
            {"symbol": "AMZN", "direction": "CALL"},
        ),
        "CANDIDATE_INSPECTION": (
            Path("candidate.json"),
            {"symbol": "AMZN", "direction": "CALL"},
        ),
        "OPTION_CHAIN": (
            Path("option_chain.json"),
            {"symbol": "AMZN", "direction": "CALL"},
        ),
        "STRATEGY_COMPARISON": (
            Path("strategy.json"),
            {
                "symbol": "AMZN",
                "direction": "CALL",
                "generated_strategies": 175,
                "ranked_strategies": 20,
            },
        ),
        "INSTITUTIONAL_DECISION": (
            Path("decision.json"),
            {
                "symbol": "AMZN",
                "direction": "CALL",
                "decision": "APPROVE",
                "paper_trade_ready": False,
            },
        ),
        "PAPER_TRADE_PREPARATION": (
            Path("preparation.json"),
            {
                "symbol": "AMZN",
                "direction": "CALL",
                "decision": "READY",
                "paper_trade_ready": True,
                "refreshed_debit": 1.30,
                "reward_risk_ratio": 2.846,
            },
        ),
        "PAPER_TRADE_LIFECYCLE": (
            Path("lifecycle.json"),
            {
                "order": {"status": "FILLED"},
                "position": {"status": "OPEN"},
                "duplicate_submission": False,
            },
        ),
        "PERFORMANCE": (
            Path("performance.json"),
            {
                "summary": {
                    "total_positions": 1,
                    "total_pnl": 20.0,
                    "win_rate": None,
                }
            },
        ),
    }

    report = DashboardWorkflowService().build_report(
        artifacts
    )

    assert report.workflow_status == "COMPLETE"
    assert report.completed_stages == 8
    assert report.total_stages == 8
    assert report.paper_trade_ready is True
    assert report.position_open is True
    assert report.performance_available is True

    print(
        "Milestone 35 Phase 5 Step 12 dashboard workflow assertions passed."
    )


if __name__ == "__main__":
    main()
