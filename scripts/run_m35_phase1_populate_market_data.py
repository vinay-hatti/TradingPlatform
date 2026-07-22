from __future__ import annotations

import argparse
from datetime import date

from trading_ai.database.session import create_session
from trading_ai.scanner.market_data_population import (
    BulkMarketDataPopulationService,
    MarketDataPopulationPolicy,
    YFinanceBulkHistoricalProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate price_history for the canonical market universe.")
    parser.add_argument("--universe-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--report-dir", default="reports/m35/phase1/market_data_population")
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--minimum-bars", type=int, default=20)
    parser.add_argument("--stale-after-days", type=int, default=7)
    parser.add_argument("--minimum-coverage-pct", type=float, default=70.0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=5.0)
    parser.add_argument("--request-pause-seconds", type=float, default=1.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--limit", type=int, help="Populate only the first N symbols for smoke testing.")
    parser.add_argument("--provider-chunk-size", type=int, default=10, help="Maximum tickers per bounded yfinance call.")
    parser.add_argument("--provider-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--yfinance-cache-dir", default="data/cache/yfinance")
    parser.add_argument("--minimum-fd-headroom", type=int, default=64)
    args = parser.parse_args()
    policy = MarketDataPopulationPolicy(
        lookback_days=args.lookback_days, minimum_bars=args.minimum_bars,
        stale_after_days=args.stale_after_days, minimum_coverage_pct=args.minimum_coverage_pct,
        batch_size=args.batch_size, max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        request_pause_seconds=args.request_pause_seconds,
        continue_on_error=not args.fail_fast,
        minimum_fd_headroom=args.minimum_fd_headroom,
    )
    session = create_session()
    try:
        provider = YFinanceBulkHistoricalProvider(
            cache_dir=args.yfinance_cache_dir,
            provider_chunk_size=args.provider_chunk_size,
            timeout_seconds=args.provider_timeout_seconds,
        )
        result = BulkMarketDataPopulationService(provider, policy).run(
            session=session, universe_csv=args.universe_csv, report_dir=args.report_dir,
            resume=args.resume, force_refresh=args.force_refresh,
            start=date.fromisoformat(args.start) if args.start else None,
            end=date.fromisoformat(args.end) if args.end else None,
            limit=args.limit,
        )
    finally:
        session.close()
    print("=========================================================")
    print("Bulk Market Data Population")
    print("=========================================================")
    print(f"Provider                         YFINANCE")
    print(f"Requested Symbols                {result.requested_symbols:>10}")
    print(f"Attempted Symbols                {result.attempted_symbols:>10}")
    print(f"Succeeded Symbols                {result.succeeded_symbols:>10}")
    print(f"Failed Symbols                   {result.failed_symbols:>10}")
    print(f"Skipped Fresh Symbols            {result.skipped_fresh_symbols:>10}")
    print(f"Rows Upserted                    {result.rows_upserted:>10}")
    print(f"Coverage                         {result.coverage.coverage_pct:>9.2f}%")
    print(f"Status                           {result.status:>10}")
    print(f"Reports                          {result.report_dir}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if result.status == "FAILED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
