from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from trading_ai.database import SessionLocal
from trading_ai.market_intelligence.publication import ScannerReadinessService


def main() -> int:
    p=argparse.ArgumentParser(description="Validate and optionally publish the current scanner-ready market state.")
    p.add_argument("--publish", action="store_true")
    p.add_argument("--run-id", default=None)
    p.add_argument("--publication-name", default="current_market_state")
    args=p.parse_args()
    run_id=args.run_id or f"readiness-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    with SessionLocal() as session:
        service=ScannerReadinessService(session)
        result=service.publish(run_id=run_id,publication_name=args.publication_name) if args.publish else service.evaluate()
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.scanner_ready else 1

if __name__ == "__main__":
    raise SystemExit(main())
