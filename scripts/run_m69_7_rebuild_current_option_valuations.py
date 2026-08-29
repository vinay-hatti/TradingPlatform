from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.publication_scope import latest_opportunity_ids
from trading_ai.option_valuation_intelligence.service import InstitutionalOptionValuationService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild M69 from the current materialized Institutional Options run."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    with SessionLocal() as session:
        stock_run_id, opportunity_ids = latest_opportunity_ids(session)
    if not stock_run_id or not opportunity_ids:
        print(json.dumps({
            "status": "FAILED",
            "reason": "NO_CURRENT_MATERIALIZED_STOCK_RUN",
            "stock_scanner_run_id": stock_run_id,
            "opportunity_count": len(opportunity_ids),
        }, indent=2, sort_keys=True))
        return 2

    if args.dry_run:
        print(json.dumps({
            "status": "READY",
            "mode": "DRY_RUN",
            "stock_scanner_run_id": stock_run_id,
            "opportunity_count": len(opportunity_ids),
        }, indent=2, sort_keys=True))
        return 0

    result = InstitutionalOptionValuationService(SessionLocal).build(
        limit=args.limit,
        opportunity_ids=opportunity_ids,
        scope="CURRENT_RUN",
    )
    output = {"stock_scanner_run_id": stock_run_id, **result}
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    anomaly = bool((result.get("diagnostics") or {}).get("distribution_anomaly"))
    return 0 if result.get("status") in {"READY", "DEGRADED"} and result.get("built", 0) > 0 and not anomaly else 3


if __name__ == "__main__":
    raise SystemExit(main())
