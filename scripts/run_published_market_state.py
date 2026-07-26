from __future__ import annotations

import argparse
import json

from trading_ai.database import SessionLocal
from trading_ai.published_state import (
    PublishedMarketStateResolver,
    PublishedStatePolicy,
    write_resolution_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the currently published market state")
    parser.add_argument("--publication-name", default="current_market_state")
    parser.add_argument("--maximum-age-hours", type=float, default=36.0)
    parser.add_argument("--warning-age-hours", type=float, default=24.0)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--consumer", choices=("generic", "scanner", "decision"), default="generic")
    parser.add_argument("--output", default="reports/published_state/current.json")
    args = parser.parse_args()

    policy = PublishedStatePolicy.for_consumer(
        args.consumer,
        publication_name=args.publication_name,
        maximum_age_seconds=max(1, int(args.maximum_age_hours * 3600)),
        warning_age_seconds=max(1, int(args.warning_age_hours * 3600)),
        allow_degraded=not args.require_ready,
    )
    with SessionLocal() as session:
        result = PublishedMarketStateResolver(session, policy).resolve()
    write_resolution_json(args.output, result)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.usable else 1


if __name__ == "__main__":
    raise SystemExit(main())
