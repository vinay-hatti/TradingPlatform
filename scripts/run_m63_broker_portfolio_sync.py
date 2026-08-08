from __future__ import annotations

import argparse
import json
import time

from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.session import SessionLocal


def run(portfolio_id: str, offline: bool) -> dict:
    return BrokerPortfolioSynchronizationService(SessionLocal).synchronize(
        portfolio_id,
        actor="m63-sync-cli",
        connect_broker=not offline,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize IBKR broker truth into Portfolio Intelligence")
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--offline", action="store_true", help="Project the latest persisted IBKR snapshot without reconnecting")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    while True:
        try:
            print(json.dumps(run(args.portfolio_id, args.offline), indent=2, sort_keys=True))
        except Exception as exc:
            print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
            if not args.daemon:
                raise
        if not args.daemon:
            break
        time.sleep(max(15, args.interval_seconds))


if __name__ == "__main__":
    main()
