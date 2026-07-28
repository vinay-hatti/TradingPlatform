from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from trading_ai.database.session import SessionLocal
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
from trading_ai.broker.ibkr.service import IbkrPaperAccountService
from trading_ai.broker.ibkr.transport import IbapiTransport


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify registered IBKR paper connectivity in read-only mode")
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    args = parser.parse_args()

    with SessionLocal() as session:
        binding = session.scalar(
            select(BrokerAccountBindingModel).where(
                BrokerAccountBindingModel.portfolio_id == args.account_id
            )
        )
        if binding is None:
            raise SystemExit(f"No IBKR binding found for {args.account_id}")
        config = IbkrPaperConnectionConfig(
            host=binding.host,
            port=binding.port,
            client_id=binding.client_id,
            environment=binding.broker_environment,
            expected_account_id=binding.broker_account_id,
            read_only=True,
        )

    transport = IbapiTransport()
    try:
        status = transport.connect(config)
        payload = {
            "status": "CONNECTED_READ_ONLY",
            "portfolio_id": args.account_id,
            "broker_account_id_masked": IbkrPaperAccountService.mask_account(config.expected_account_id),
            "environment": status.environment,
            "server_version": status.server_version,
            "managed_account_count": len(status.account_ids),
            "live_trading_enabled": False,
            "order_submission_enabled": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        transport.disconnect()


if __name__ == "__main__":
    main()
