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
    AutomatedPaperTradingPhaseService,
    write_handoff_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 1 complete automated paper-trading workflow."
    )
    parser.add_argument("--institutional-report", required=True)
    parser.add_argument("--portfolio-exposure-json", required=True)
    parser.add_argument("--mode", choices=("DRY_RUN", "SUBMIT"), default="DRY_RUN")
    parser.add_argument("--maximum-orders", type=int, default=10)
    parser.add_argument("--confirmation", default="")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase1/phase1_automated_paper_trading.json",
    )
    return parser.parse_args()


def load_binding() -> BrokerAccountBindingModel:
    with SessionLocal() as session:
        binding = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == "PAPER-PRIMARY",
                BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
            )
        )
        if binding is None:
            raise KeyError("IBKR binding not found for PAPER-PRIMARY")
        session.expunge(binding)
        return binding


def main() -> None:
    args = parse_args()
    institutional_payload = json.loads(
        Path(args.institutional_report).read_text(encoding="utf-8")
    )
    exposure_payload = json.loads(
        Path(args.portfolio_exposure_json).read_text(encoding="utf-8")
    )

    def exposure_provider(portfolio_id: str):
        actual = str(exposure_payload.get("portfolio_id", portfolio_id))
        if actual != portfolio_id:
            raise ValueError(
                f"portfolio exposure belongs to {actual}, expected {portfolio_id}"
            )
        return exposure_payload

    transport = None
    broker_service = None
    connection = {
        "status": "NOT_CONNECTED_DRY_RUN",
        "environment": "PAPER",
        "live_trading_enabled": False,
    }
    try:
        if args.mode == "SUBMIT":
            binding = load_binding()
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

        service = AutomatedPaperTradingPhaseService(
            SessionLocal,
            exposure_provider=exposure_provider,
            broker_order_service=broker_service,
        )
        result = service.execute(
            institutional_payload,
            mode=args.mode,
            confirmation=args.confirmation,
            maximum_orders=args.maximum_orders,
        )
        output = result.to_dict()
        output["connection"] = connection
        path = write_handoff_report(output, args.output_json)
        output["report_path"] = str(path)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        if result.status in {
            "NO_APPROVED_INSTITUTIONAL_DECISIONS",
            "PHASE1_BLOCKED_BY_PORTFOLIO_EXPOSURE",
        }:
            raise SystemExit(2)
    finally:
        if transport is not None:
            transport.disconnect()


if __name__ == "__main__":
    main()
