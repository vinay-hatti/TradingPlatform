from __future__ import annotations

import argparse
import json

from trading_ai.broker.ibkr import IbkrPaperAccountService
from trading_ai.database.session import create_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Register an IBKR paper account without connecting or storing credentials.")
    parser.add_argument("--internal-account-id", default="PAPER-PRIMARY")
    parser.add_argument("--broker-account-id", required=True, help="IBKR paper account identifier; expected to begin with DU")
    parser.add_argument("--base-currency", default="USD")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=50)
    args = parser.parse_args()
    result = IbkrPaperAccountService(create_session).register(
        portfolio_id=args.internal_account_id,
        broker_account_id=args.broker_account_id,
        base_currency=args.base_currency,
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        read_only=True,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
