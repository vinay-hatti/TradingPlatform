from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.broker.broker_operational_reporting import (
    BrokerOperationalReport,
)


def main() -> None:
    readiness = {
        "broker": "fake",
        "environment": "paper",
        "allowed": True,
        "score": 100.0,
        "grade": "A",
        "recommendation": "READY",
        "account": {
            "account_id": "PAPER-001",
            "buying_power": 200000.0,
            "option_buying_power": 100000.0,
        },
        "authentication": {"session_id": "session-001"},
    }
    execution = (
        {
            "action": "SUBMIT",
            "client_order_id": "order-001",
            "broker_order_id": "broker-001",
            "status": "ACCEPTED",
            "allowed": True,
            "replayed": False,
            "score": 100.0,
            "recommendation": "ACCEPT",
        },
    )
    summaries = (
        {
            "broker_order_id": "broker-001",
            "client_order_id": "order-001",
            "status": "FILLED",
            "ordered_quantity": 2,
            "filled_quantity": 2,
            "remaining_quantity": 0,
            "average_fill_price": 5.0,
            "commission": 1.30,
            "fees": 0.10,
        },
    )
    reconciliation = {
        "matched_position_count": 1,
        "rejected_position_count": 0,
        "score": 100.0,
        "recommendation": "ACCEPT",
        "position_profiles": (
            {
                "symbol": "AAPL_OPTION",
                "allowed": True,
                "score": 100.0,
                "recommendation": "ACCEPT",
                "quantity_difference": 0,
                "average_cost_difference_pct": 0,
                "broker_position": {"quantity": 2},
                "platform_position": {"quantity": 2},
            },
        ),
    }

    report = BrokerOperationalReport()
    assert "Broker Authentication and Readiness" in report.readiness_html(readiness)
    assert "Order Submission, Cancellation, Replacement, and Idempotency" in report.order_execution_html(execution)
    assert "Order Status, Fills, Commissions, and Fees" in report.order_status_html(summaries)
    assert "Position Synchronization and Reconciliation" in report.positions_html(reconciliation)

    with tempfile.TemporaryDirectory() as temp:
        path = report.generate(
            readiness_profile=readiness,
            execution_results=execution,
            order_summaries=summaries,
            reconciliation_summary=reconciliation,
            path=Path(temp) / "broker_report.html",
        )
        html = path.read_text(encoding="utf-8")
        assert "Live Broker Integration and Operations" in html
        assert "PAPER-001" in html
        assert "broker-001" in html
        assert "AAPL_OPTION" in html

    print("All broker operational reporting assertions passed.")


if __name__ == "__main__":
    main()
