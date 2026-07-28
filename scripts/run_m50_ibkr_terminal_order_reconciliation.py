from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr import (
    IbapiPaperOrderTransport,
    IbkrPaperConnectionConfig,
    IbkrPaperOrderGovernanceService,
    IbkrPaperOrderService,
)
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel, BrokerOrderModel
from trading_ai.database.session import SessionLocal


TERMINAL_CANONICAL_STATES = {"FILLED", "CANCELED", "REJECTED"}
TERMINAL_BROKER_STATUSES = {
    "FILLED", "CANCELLED", "CANCELED", "APICANCELLED", "INACTIVE", "REJECTED"
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reconcile IBKR paper orders, including terminal completed orders."
    )
    p.add_argument("--account-id", default="PAPER-PRIMARY")
    p.add_argument("--aggregate-id")
    p.add_argument("--poll-seconds", type=float, default=2.0)
    p.add_argument("--max-attempts", type=int, default=5)
    p.add_argument(
        "--require-terminal",
        action="store_true",
        help="Fail unless the selected aggregate reaches a terminal state.",
    )
    return p


def load_binding(portfolio_id: str) -> BrokerAccountBindingModel:
    with SessionLocal() as session:
        row = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == portfolio_id,
                BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
            )
        )
        if row is None:
            raise LookupError(f"IBKR binding not found for {portfolio_id}")
        session.expunge(row)
        return row


def snapshot(portfolio_id: str, aggregate_id: str | None) -> dict:
    with SessionLocal() as session:
        query = select(BrokerOrderModel).where(
            BrokerOrderModel.portfolio_id == portfolio_id
        )
        if aggregate_id:
            query = query.where(BrokerOrderModel.aggregate_id == aggregate_id)
        rows = list(session.scalars(query.order_by(BrokerOrderModel.updated_at.desc())).all())
        output = []
        for broker in rows:
            canonical = session.get(CanonicalOrderModel, broker.aggregate_id)
            output.append(
                {
                    "aggregate_id": broker.aggregate_id,
                    "broker_order_id": broker.broker_order_id,
                    "broker_status": broker.status,
                    "broker_filled_quantity": broker.filled_quantity,
                    "broker_remaining_quantity": broker.remaining_quantity,
                    "canonical_state": None if canonical is None else canonical.state,
                    "canonical_terminal_at": None if canonical is None else canonical.terminal_at,
                    "updated_at": broker.updated_at,
                }
            )
        return {"count": len(output), "orders": output}


def is_terminal(data: dict, aggregate_id: str) -> bool:
    for row in data["orders"]:
        if row["aggregate_id"] != aggregate_id:
            continue
        broker_terminal = str(row["broker_status"]).upper().replace(" ", "") in TERMINAL_BROKER_STATUSES
        canonical_terminal = row["canonical_state"] in TERMINAL_CANONICAL_STATES
        return broker_terminal or canonical_terminal
    return False


def main() -> None:
    args = parser().parse_args()
    if args.max_attempts < 1:
        raise ValueError("--max-attempts must be at least 1")
    if args.require_terminal and not args.aggregate_id:
        raise ValueError("--require-terminal requires --aggregate-id")

    governance = IbkrPaperOrderGovernanceService(SessionLocal)
    control = governance.status(args.account_id)
    if control["environment"] != "PAPER" or control["live_trading_enabled"]:
        raise RuntimeError("paper-only safety check failed")

    binding = load_binding(args.account_id)
    transport = IbapiPaperOrderTransport()
    service = IbkrPaperOrderService(SessionLocal, transport)
    report = {
        "milestone": 50,
        "phase": "TERMINAL_IBKR_PAPER_ORDER_RECONCILIATION",
        "portfolio_id": args.account_id,
        "aggregate_id": args.aggregate_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "control_before": control,
        "attempts": [],
    }

    try:
        report["connection"] = transport.connect(
            IbkrPaperConnectionConfig(
                host=binding.host,
                port=binding.port,
                client_id=binding.client_id,
                environment="PAPER",
                expected_account_id=binding.broker_account_id,
                timeout_seconds=15.0,
                read_only=False,
            )
        )
        for attempt in range(1, args.max_attempts + 1):
            sync = service.synchronize(args.account_id)
            current = snapshot(args.account_id, args.aggregate_id)
            report["attempts"].append(
                {"attempt": attempt, "synchronize": sync, "database": current}
            )
            if args.aggregate_id and is_terminal(current, args.aggregate_id):
                break
            if attempt < args.max_attempts:
                time.sleep(max(0.0, args.poll_seconds))

        report["database_after"] = snapshot(args.account_id, args.aggregate_id)
        terminal = bool(
            args.aggregate_id and is_terminal(report["database_after"], args.aggregate_id)
        )
        report["terminal_state_reached"] = terminal
        if args.require_terminal and not terminal:
            report["status"] = "TERMINAL_STATE_NOT_OBSERVED"
            print(json.dumps(report, indent=2, sort_keys=True, default=str))
            raise SystemExit(2)
        report["status"] = "RECONCILIATION_COMPLETED"
    finally:
        transport.disconnect()
        report["control_after"] = governance.status(args.account_id)

    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
