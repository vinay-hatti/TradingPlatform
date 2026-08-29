from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from trading_ai.broker.ibkr import (
    IbapiPaperOrderTransport,
    IbkrPaperConnectionConfig,
)
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
from trading_ai.database.session import SessionLocal
from trading_ai.paper_trading.automated_lifecycle import (
    AutomatedOrderLifecyclePolicy,
    AutomatedPaperOrderLifecycleService,
    write_lifecycle_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 2 automated IBKR paper-order lifecycle."
    )
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    parser.add_argument(
        "--mode",
        choices=("MONITOR", "CANCEL_STALE"),
        default="MONITOR",
    )
    parser.add_argument("--stale-submitted-minutes", type=int, default=30)
    parser.add_argument("--stale-partial-fill-minutes", type=int, default=60)
    parser.add_argument("--maximum-cancellations", type=int, default=10)
    parser.add_argument("--confirmation", default="")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase2/automated_order_lifecycle.json",
    )
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    binding = load_binding(args.account_id)
    policy = AutomatedOrderLifecyclePolicy(
        automatic_cancellation_enabled=args.mode == "CANCEL_STALE",
        stale_submitted_minutes=args.stale_submitted_minutes,
        stale_partial_fill_minutes=args.stale_partial_fill_minutes,
        maximum_cancel_actions_per_run=args.maximum_cancellations,
    )
    transport = IbapiPaperOrderTransport()
    try:
        connection = transport.connect(
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
        service = AutomatedPaperOrderLifecycleService(
            SessionLocal,
            transport,
            policy=policy,
        )
        result = service.execute(
            args.account_id,
            mode=args.mode,
            confirmation=args.confirmation,
        )
        output = result.to_dict()
        output["connection"] = connection
        path = write_lifecycle_report(output, args.output_json)
        output["report_path"] = str(path)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    finally:
        transport.disconnect()


if __name__ == "__main__":
    main()
