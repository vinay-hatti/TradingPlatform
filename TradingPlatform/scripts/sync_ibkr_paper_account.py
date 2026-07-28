from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.broker.ibkr.reconciliation import IbkrPaperReconciliationService
from trading_ai.broker.ibkr.service import IbkrPaperAccountService
from trading_ai.broker.ibkr.transport import IbapiTransport


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize and reconcile a registered IBKR paper account")
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    parser.add_argument("--no-import-positions", action="store_true")
    args = parser.parse_args()

    account = IbkrPaperAccountService(SessionLocal, IbapiTransport()).verify_and_sync(args.account_id)
    reconciliation = IbkrPaperReconciliationService(SessionLocal).reconcile(
        args.account_id,
        import_positions=not args.no_import_positions,
    )
    print(json.dumps({"account_sync": account, "reconciliation": reconciliation}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
