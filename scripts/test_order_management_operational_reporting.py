from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.order_management.order_management_reporting import (
    OrderManagementOperationalReport,
)


def main() -> None:
    aggregates = (
        {
            "aggregate_id": "agg-001",
            "client_order_id": "client-001",
            "account_id": "PAPER-001",
            "state": "SUBMITTED",
            "version": 4,
            "total_quantity": 2,
            "filled_quantity": 0,
            "remaining_quantity": 2,
            "broker_order_id": "broker-001",
        },
    )
    workflows = (
        {
            "allowed": True,
            "action": "SUBMIT",
            "aggregate_id": "agg-001",
            "state": "SUBMITTED",
            "aggregate_version": 4,
            "recommendation": "MONITOR",
            "routing_decision": {
                "route_id": "paper",
                "broker": "fake",
            },
        },
    )
    replays = (
        {
            "allowed": True,
            "aggregate_id": "agg-001",
            "event_count": 4,
            "final_version": 4,
            "final_state": "SUBMITTED",
        },
    )
    audit = {"valid": True, "errors": ()}
    groups = (
        {
            "group_id": "bracket-001",
            "group_type": "BRACKET",
            "account_id": "PAPER-001",
            "root_aggregate_id": "agg-001",
            "state": "ACTIVE",
            "members": (
                {"aggregate_id": "agg-001", "role": "ENTRY"},
                {"aggregate_id": "tp-001", "role": "TAKE_PROFIT"},
                {"aggregate_id": "sl-001", "role": "STOP_LOSS"},
            ),
        },
    )
    checkpoints = (
        {
            "checkpoint_id": "recovery-001",
            "aggregate_id": "agg-001",
            "workflow_action": "REPLACE",
            "state": "COMPLETED",
            "completed_steps": (
                "CANONICAL_REPLACE_REQUEST",
                "BROKER_REPLACE",
                "CANONICAL_REPLACE_COMPLETE",
            ),
            "pending_steps": (),
            "retry_count": 0,
            "recoverable": True,
        },
    )

    report = OrderManagementOperationalReport()
    assert "Canonical Order Aggregates and Lifecycle" in report.aggregates_html(aggregates)
    assert "Command Handling, Broker Routing, and Workflow Orchestration" in report.routing_html(workflows)
    assert "Repository, Event Journal, Audit Ledger, and Concurrency" in report.persistence_html(journal_replays=replays, audit_status=audit)
    assert "Parent/Child, Bracket, and OCO Order Groups" in report.groups_html(groups)
    assert "Cancel, Replace, and Recovery Governance" in report.recovery_html(checkpoints)

    with tempfile.TemporaryDirectory() as temp:
        path = report.generate(
            aggregates=aggregates,
            workflow_results=workflows,
            journal_replays=replays,
            audit_status=audit,
            order_groups=groups,
            recovery_checkpoints=checkpoints,
            path=Path(temp) / "order_management.html",
        )
        html = path.read_text(encoding="utf-8")
        assert "Order Management System Operations" in html
        assert "agg-001" in html
        assert "bracket-001" in html
        assert "recovery-001" in html
        assert "VALID" in html

    print("All order-management operational reporting assertions passed.")


if __name__ == "__main__":
    main()
