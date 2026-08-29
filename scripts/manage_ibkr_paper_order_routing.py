from __future__ import annotations

import argparse
import json

from trading_ai.broker.ibkr import IbkrPaperOrderGovernanceService
from trading_ai.database.session import SessionLocal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, activate, or disable IBKR paper-order routing."
    )
    parser.add_argument("action", choices=["status", "activate", "disable"])
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--reason", default="operator request")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    governance = IbkrPaperOrderGovernanceService(SessionLocal)

    if args.action == "activate":
        result = governance.activate(
            args.account_id,
            confirmation=args.confirmation,
        )
    elif args.action == "disable":
        result = governance.disable(
            args.account_id,
            reason=args.reason,
        )
    else:
        result = governance.status(args.account_id)

    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
