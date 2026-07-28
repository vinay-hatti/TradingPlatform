from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr import (
    IbapiPaperOrderTransport,
    IbkrPaperConnectionConfig,
    IbkrPaperOrderGovernanceService,
    IbkrPaperOrderRequest,
    IbkrPaperOrderService,
)
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel, BrokerOrderModel
from trading_ai.database.session import SessionLocal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one governed IBKR paper submit/replay/sync/cancel smoke test.")
    p.add_argument("--account-id", default="PAPER-PRIMARY")
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    p.add_argument("--quantity", type=float, default=1.0)
    p.add_argument("--limit-price", type=float, required=True)
    p.add_argument("--primary-exchange", default="NASDAQ")
    p.add_argument("--wait-seconds", type=float, default=2.0)
    p.add_argument("--terminal-poll-attempts", type=int, default=5)
    p.add_argument("--confirmation", required=True)
    p.add_argument("--keep-order-open", action="store_true", help="Skip cancellation; not recommended.")
    return p


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


def create_canonical_order(*, aggregate_id: str, client_order_id: str, args: argparse.Namespace) -> None:
    now = utc_now()
    session = SessionLocal()
    try:
        session.add(
            CanonicalOrderModel(
                aggregate_id=aggregate_id,
                client_order_id=client_order_id,
                account_id=args.account_id,
                idempotency_key=f"m50-smoke:{aggregate_id}",
                order_type="LMT",
                time_in_force="DAY",
                state="CREATED",
                version=1,
                total_quantity=args.quantity,
                filled_quantity=0.0,
                remaining_quantity=args.quantity,
                average_fill_price=None,
                limit_price=args.limit_price,
                stop_price=None,
                outside_regular_hours=False,
                strategy_name="M50_IBKR_CONTROLLED_SMOKE_TEST",
                broker_order_id=None,
                parent_aggregate_id=None,
                root_aggregate_id=aggregate_id,
                replace_count=0,
                legs_json=[{
                    "leg_id": "LEG-1",
                    "symbol": args.symbol.upper(),
                    "side": args.side,
                    "quantity": args.quantity,
                    "security_type": "STK",
                }],
                created_at=now,
                updated_at=now,
                terminal_at=None,
                last_event_id=None,
                metadata_json={
                    "milestone": 50,
                    "purpose": "CONTROLLED_IBKR_PAPER_ORDER_SMOKE_TEST",
                    "paper_only": True,
                    "live_trading_enabled": False,
                },
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def database_snapshot(aggregate_id: str) -> dict:
    session = SessionLocal()
    try:
        canonical = session.get(CanonicalOrderModel, aggregate_id)
        broker = session.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id == aggregate_id))
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
                "broker_order_id": broker.broker_order_id,
                "permanent_id": broker.permanent_id,
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
    args = parser().parse_args()
    expected = f"RUN IBKR PAPER ORDER SMOKE TEST {args.account_id}"
    if args.confirmation.strip() != expected:
        raise ValueError(f"confirmation must exactly equal: {expected}")
    if args.limit_price <= 0 or args.quantity <= 0:
        raise ValueError("limit price and quantity must be positive")

    governance = IbkrPaperOrderGovernanceService(SessionLocal)
    control = governance.status(args.account_id)
    if control["environment"] != "PAPER" or control["live_trading_enabled"]:
        raise RuntimeError("paper-only safety check failed")
    if not control["paper_order_submission_enabled"] or control["read_only"]:
        raise RuntimeError("governed paper-order routing is not enabled")

    binding = load_binding(args.account_id)
    if not binding.broker_account_id.upper().startswith("DU"):
        raise RuntimeError("registered broker account is not an IBKR paper account")

    suffix = uuid.uuid4().hex[:12].upper()
    aggregate_id = f"M50-SMOKE-{suffix}"
    client_order_id = f"M50-SMOKE-CLIENT-{suffix}"
    create_canonical_order(aggregate_id=aggregate_id, client_order_id=client_order_id, args=args)

    request = IbkrPaperOrderRequest(
        aggregate_id=aggregate_id,
        client_order_id=client_order_id,
        portfolio_id=args.account_id,
        broker_account_id=binding.broker_account_id,
        symbol=args.symbol.upper(),
        security_type="STK",
        side=args.side,
        quantity=args.quantity,
        order_type="LMT",
        time_in_force="DAY",
        limit_price=args.limit_price,
        currency=binding.base_currency or "USD",
        exchange="SMART",
        primary_exchange=args.primary_exchange,
        outside_regular_hours=False,
        transmit=True,
        metadata={"milestone": 50, "smoke_test": True, "paper_only": True},
    )

    transport = IbapiPaperOrderTransport()
    service = IbkrPaperOrderService(SessionLocal, transport)
    report: dict[str, object] = {
        "milestone": 50,
        "phase": "CONTROLLED_IBKR_PAPER_ORDER_SMOKE_TEST",
        "aggregate_id": aggregate_id,
        "portfolio_id": args.account_id,
        "symbol": args.symbol.upper(),
        "side": args.side,
        "quantity": args.quantity,
        "limit_price": args.limit_price,
        "environment": "PAPER",
        "live_trading_enabled": False,
        "control_before": control,
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
        submitted = service.submit(request)
        replayed = service.submit(request)
        report["submitted"] = submitted
        report["idempotent_replay"] = replayed
        if not replayed.get("replayed") or replayed.get("broker_order_id") != submitted.get("broker_order_id"):
            raise AssertionError("idempotent replay protection failed")

        time.sleep(max(0.0, args.wait_seconds))
        report["synchronize_after_submit"] = service.synchronize(args.account_id)
        report["database_after_submit"] = database_snapshot(aggregate_id)

        if args.keep_order_open:
            report["cancellation"] = "SKIPPED_BY_OPERATOR"
            report["status"] = "SMOKE_TEST_SUBMITTED_ORDER_LEFT_OPEN"
        else:
            report["cancel_requested"] = service.cancel(args.account_id, aggregate_id)
            terminal_states = {"CANCELED", "FILLED", "REJECTED"}
            terminal_observed = False
            report["terminal_reconciliation_attempts"] = []
            for attempt in range(1, max(1, args.terminal_poll_attempts) + 1):
                time.sleep(max(0.0, args.wait_seconds))
                sync_result = service.synchronize(args.account_id)
                snapshot = database_snapshot(aggregate_id)
                report["terminal_reconciliation_attempts"].append({
                    "attempt": attempt,
                    "synchronize": sync_result,
                    "database": snapshot,
                })
                canonical_state = (snapshot.get("canonical") or {}).get("state")
                if canonical_state in terminal_states:
                    terminal_observed = True
                    break
            report["synchronize_after_cancel"] = report["terminal_reconciliation_attempts"][-1]["synchronize"]
            report["database_after_cancel"] = database_snapshot(aggregate_id)
            report["terminal_state_observed"] = terminal_observed
            report["status"] = (
                "SMOKE_TEST_COMPLETED"
                if terminal_observed
                else "SMOKE_TEST_COMPLETED_TERMINAL_STATE_PENDING"
            )
    except Exception as exc:
        report["status"] = "SMOKE_TEST_FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["database_at_failure"] = database_snapshot(aggregate_id)
        raise
    finally:
        try:
            transport.disconnect()
        finally:
            report["control_after"] = governance.status(args.account_id)
            print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
