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
from trading_ai.paper_trading.automated_position_management import (
    AutomatedPositionManagementPolicy,
    AutomatedPositionManagementService,
    write_position_management_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 3 automated paper-position management."
    )
    parser.add_argument("--lifecycle-report", required=True)
    parser.add_argument("--market-prices-json", required=True)
    parser.add_argument("--mode", choices=("DRY_RUN", "SUBMIT"), default="DRY_RUN")
    parser.add_argument("--take-profit-pct", type=float, default=20.0)
    parser.add_argument("--stop-loss-pct", type=float, default=-10.0)
    parser.add_argument("--maximum-holding-minutes", type=int, default=10080)
    parser.add_argument("--option-exit-dte", type=int, default=3)
    parser.add_argument("--maximum-exit-orders", type=int, default=10)
    parser.add_argument("--confirmation", default="")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase3/automated_position_management.json",
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
    lifecycle = json.loads(
        Path(args.lifecycle_report).read_text(encoding="utf-8")
    )
    market_prices = json.loads(
        Path(args.market_prices_json).read_text(encoding="utf-8")
    )
    portfolio_id = str(lifecycle.get("portfolio_id") or "PAPER-PRIMARY")
    policy = AutomatedPositionManagementPolicy(
        take_profit_pct=args.take_profit_pct,
        stop_loss_pct=args.stop_loss_pct,
        maximum_holding_minutes=args.maximum_holding_minutes,
        option_exit_dte=args.option_exit_dte,
        maximum_exit_orders_per_run=args.maximum_exit_orders,
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
            binding = load_binding(portfolio_id)
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

        service = AutomatedPositionManagementService(
            SessionLocal,
            policy=policy,
            broker_order_service=broker_service,
        )
        result = service.execute(
            lifecycle,
            market_prices,
            mode=args.mode,
            confirmation=args.confirmation,
        )
        output = result.to_dict()
        output["connection"] = connection
        path = write_position_management_report(output, args.output_json)
        output["report_path"] = str(path)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    finally:
        if transport is not None:
            transport.disconnect()


if __name__ == "__main__":
    main()
