from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from trading_ai.broker.ibkr import (
    IbapiPaperOrderTransport,
    IbkrPaperConnectionConfig,
    IbkrPaperOrderService,
)
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
from trading_ai.database.session import SessionLocal
from trading_ai.paper_trading.automated_order_handoff import (
    InstitutionalDecisionBatchHandoffService,
    write_handoff_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 51 Phase 1 Step 2: convert institutional scanner "
            "decisions into governed IBKR paper-order handoffs."
        )
    )
    parser.add_argument("--institutional-report", required=True)
    parser.add_argument("--mode", choices=("DRY_RUN", "SUBMIT"), default="DRY_RUN")
    parser.add_argument("--maximum-orders", type=int, default=10)
    parser.add_argument("--confirmation", default="")
    parser.add_argument(
        "--output-json",
        default=(
            "reports/m51/phase1/step2/"
            "institutional_decision_handoff.json"
        ),
    )
    return parser.parse_args()


def load_binding(portfolio_id: str) -> BrokerAccountBindingModel:
    with SessionLocal() as session:
        binding = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == portfolio_id,
                BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
            )
        )
        if binding is None:
            raise KeyError(f"IBKR binding not found for {portfolio_id}")
        session.expunge(binding)
        return binding


def main() -> None:
    args = parse_args()
    payload = json.loads(
        Path(args.institutional_report).read_text(encoding="utf-8")
    )
    transport = None
    broker_service = None
    connection = {
        "status": "NOT_CONNECTED_DRY_RUN",
        "environment": "PAPER",
        "live_trading_enabled": False,
    }
    try:
        if args.mode == "SUBMIT":
            binding = load_binding("PAPER-PRIMARY")
            transport = IbapiPaperOrderTransport()
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
            broker_service = IbkrPaperOrderService(SessionLocal, transport)

        service = InstitutionalDecisionBatchHandoffService(
            SessionLocal,
            broker_order_service=broker_service,
        )
        result = service.execute(
            payload,
            mode=args.mode,
            confirmation=args.confirmation,
            maximum_orders=args.maximum_orders,
        )
        output = result.to_dict()
        output["connection"] = connection
        report_path = write_handoff_report(output, args.output_json)
        output["report_path"] = str(report_path)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        if result.status == "NO_APPROVED_INSTITUTIONAL_DECISIONS":
            raise SystemExit(2)
    finally:
        if transport is not None:
            transport.disconnect()


if __name__ == "__main__":
    main()
