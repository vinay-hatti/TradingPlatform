from pathlib import Path

from trading_ai.scanner.dashboard.dashboard_workflow_service import (
    DashboardWorkflowService,
)


def main() -> None:
    report = DashboardWorkflowService().build_report(
        {
            "INSTITUTIONAL_DECISION": (
                Path("decision.json"),
                {
                    "symbol": "AMZN",
                    "direction": "CALL",
                    "decision": "APPROVE",
                },
            )
        }
    )

    assert report.workflow_status == "INCOMPLETE"
    assert report.completed_stages == 1
    assert (
        "DASHBOARD_WORKFLOW_NOT_FULLY_COMPLETE"
        in report.warnings
    )

    print(
        "Milestone 35 Phase 5 Step 12 incomplete-workflow assertions passed."
    )


if __name__ == "__main__":
    main()
