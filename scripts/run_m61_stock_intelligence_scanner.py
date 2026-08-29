from __future__ import annotations

import argparse
from datetime import datetime, timezone

from trading_ai.database.session import SessionLocal
from trading_ai.stock_intelligence.publication_service import (
    StockIntelligencePublicationService,
    StockPublicationRequest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish Milestone 61 Stock Intelligence from persisted Polygon state."
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols")
    parser.add_argument("--publication-name", default="current_stock_intelligence")
    parser.add_argument("--market-publication-name", default="current_market_state")
    parser.add_argument("--minimum-score", type=float, default=0.0)
    parser.add_argument("--top", type=int, default=0, help="Maximum published candidates; 0 publishes all analyzed symbols")
    parser.add_argument("--lookback-days", type=int, default=750)
    parser.add_argument("--snapshot-timestamp", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbols = tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip())
    request = StockPublicationRequest(
        symbols=symbols,
        publication_name=args.publication_name,
        market_publication_name=args.market_publication_name,
        minimum_score=args.minimum_score,
        top=None if args.top <= 0 else args.top,
        lookback_days=args.lookback_days,
        snapshot_timestamp=args.snapshot_timestamp or datetime.now(timezone.utc).isoformat(),
    )
    with SessionLocal() as session:
        result = StockIntelligencePublicationService(session).publish(request)
    print("========== Milestone 61 Stock Intelligence ==========")
    print("source: persisted Polygon price_history + persisted market/trend/dealer/forecast intelligence")
    print("timeframes: 1d, 1w, 1mo (derived from persisted daily OHLCV)")
    for key in (
        "run_id", "publication_id", "publication_name", "snapshot_timestamp",
        "status", "candidate_count", "symbols_requested", "symbols_analyzed",
    ):
        print(f"{key}: {result.get(key)}")
    if result.get("failures"):
        print(f"failures: {result['failures']}")
    return 0 if result["status"] in {"READY", "DEGRADED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
