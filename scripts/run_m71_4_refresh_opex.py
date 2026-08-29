from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.opex_intelligence.service import OpexIntelligenceService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the governed M71.4 OPEX authority refresh."
    )
    parser.add_argument("--cycles", type=int, default=3, choices=range(1, 7))
    args = parser.parse_args()
    result = OpexIntelligenceService(SessionLocal).refresh(cycles=args.cycles)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if result.get("status") == "READY" and result.get("cycle_outcome") in {
        "AUTHORITY_REBUILT",
        "NOOP_UNCHANGED_AUTHORITY",
    }:
        return 0
    if result.get("status") == "BUSY_DEFERRED":
        return 75
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
