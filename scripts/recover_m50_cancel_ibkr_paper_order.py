from __future__ import annotations

import argparse
import json
import time

from sqlalchemy import select

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr import (
    IbapiPaperOrderTransport,
    IbkrPaperConnectionConfig,
    IbkrPaperOrderGovernanceService,
    IbkrPaperOrderService,
)
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerOrderModel,
)
from trading_ai.database.session import SessionLocal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recover and cancel a persisted Milestone 50 IBKR paper order."
    )
    parser.add_argument("aggregate_id")
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    parser.add_argument("--wait-seconds", type=float, default=3.0)
    parser.add_argument(
        "--confirmation",
        required=True,
        help="Exact value: CANCEL IBKR PAPER ORDER <aggregate-id>",
    )
    return parser


def load_binding(portfolio_id: str) -> BrokerAccountBindingModel:
    session = SessionLocal()
    try:
        binding = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == portfolio_id,
                BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
            )
        )
        if binding is None:
            raise LookupError(f"IBKR binding not found for {portfolio_id}")
        session.expunge(binding)
        return binding
    finally:
        session.close()


def order_snapshot(portfolio_id: str, aggregate_id: str) -> dict:
    session = SessionLocal()
    try:
        canonical = session.get(CanonicalOrderModel, aggregate_id)
        broker = session.scalar(
            select(BrokerOrderModel).where(
                BrokerOrderModel.portfolio_id == portfolio_id,
                BrokerOrderModel.aggregate_id == aggregate_id,
            )
        )
        return {
            "canonical": None if canonical is None else {
                "aggregate_id": canonical.aggregate_id,
                "state": canonical.state,
                "broker_order_id": canonical.broker_order_id,
                "filled_quantity": canonical.filled_quantity,
                "remaining_quantity": canonical.remaining_quantity,
                "average_fill_price": canonical.average_fill_price,
                "updated_at": canonical.updated_at,
            },
            "broker": None if broker is None else {
                "broker_order_record_id": broker.broker_order_record_id,
                "aggregate_id": broker.aggregate_id,
                "broker_order_id": broker.broker_order_id,
                "status": broker.status,
                "filled_quantity": broker.filled_quantity,
                "remaining_quantity": broker.remaining_quantity,
                "average_fill_price": broker.average_fill_price,
                "updated_at": broker.updated_at,
            },
        }
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    expected = f"CANCEL IBKR PAPER ORDER {args.aggregate_id}"
    if args.confirmation != expected:
        raise ValueError(f"confirmation must exactly equal: {expected}")

    governance = IbkrPaperOrderGovernanceService(SessionLocal)
    control_before = governance.status(args.account_id)
    if control_before["environment"] != "PAPER":
        raise RuntimeError("recovery cancellation requires PAPER environment")
    if control_before["live_trading_enabled"]:
        raise RuntimeError("live trading must remain disabled")
    if not control_before["paper_order_submission_enabled"]:
        raise RuntimeError("paper-order routing must be enabled for cancellation")

    binding = load_binding(args.account_id)
    config = IbkrPaperConnectionConfig(
        host=binding.host,
        port=binding.port,
        client_id=binding.client_id,
        environment=binding.broker_environment,
        expected_account_id=binding.broker_account_id,
        timeout_seconds=15.0,
        read_only=False,
    )

    transport = IbapiPaperOrderTransport()
    service = IbkrPaperOrderService(SessionLocal, transport=transport)
    report: dict[str, object] = {
        "milestone": 50,
        "phase": "IBKR_PAPER_ORDER_CANCEL_RECOVERY",
        "portfolio_id": args.account_id,
        "aggregate_id": args.aggregate_id,
        "control_before": control_before,
        "database_before": order_snapshot(args.account_id, args.aggregate_id),
        "live_trading_enabled": False,
    }

    try:
        report["connection"] = transport.connect(config)
        report["cancel_requested"] = service.cancel(
            args.account_id,
            args.aggregate_id,
        )
        time.sleep(max(0.0, args.wait_seconds))
        report["synchronized"] = service.synchronize(args.account_id)
        report["database_after"] = order_snapshot(
            args.account_id,
            args.aggregate_id,
        )
        report["status"] = "CANCEL_RECOVERY_COMPLETED"
    except Exception as exc:
        report["status"] = "CANCEL_RECOVERY_FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["database_at_failure"] = order_snapshot(
            args.account_id,
            args.aggregate_id,
        )
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        raise
    finally:
        transport.disconnect()
        report["control_after"] = governance.status(args.account_id)

    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
