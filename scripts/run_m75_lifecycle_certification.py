#!/usr/bin/env python
from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.lifecycle_governance import LifecycleGovernanceService


def main() -> int:
    ap = argparse.ArgumentParser(description="M75 lifecycle governance certification and safe terminal-position repair")
    ap.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    ap.add_argument("--repair-safe", action="store_true", help="Finalize only safe local terminal artifacts before certification")
    ap.add_argument("--actor", default="M75_CERTIFICATION")
    args = ap.parse_args()
    with SessionLocal() as session:
        result = LifecycleGovernanceService(session).certify(
            portfolio_id=args.portfolio_id,
            actor=args.actor,
            repair_safe=args.repair_safe,
        )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("audit", {}).get("status") == "CERTIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
