#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService


def main() -> None:
    parser = argparse.ArgumentParser(description="M74.14 repair of legacy canonical-order-missing autonomous exit failures")
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        result = DynamicPositionManagementService(session).repair_legacy_submission_failures(
            portfolio_id=args.portfolio_id,
            actor="M74_14_REPAIR",
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
