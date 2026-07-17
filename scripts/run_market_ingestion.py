from __future__ import annotations

import argparse

from trading_ai.market.downloader import MarketDownloader
from trading_ai.market.universe import SP500


def _symbols(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple(SP500)
    return tuple(s.strip().upper() for s in value.split(",") if s.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download historical market data with rate-limit pacing and retry."
    )
    parser.add_argument("--symbols")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--lookback-days", type=int, default=730)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--request-interval", type=float, default=15.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--initial-backoff", type=float, default=30.0)
    parser.add_argument("--max-backoff", type=float, default=300.0)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloader = MarketDownloader(
        max_workers=args.max_workers,
        request_interval_seconds=args.request_interval,
        max_retries=args.max_retries,
        initial_backoff_seconds=args.initial_backoff,
        max_backoff_seconds=args.max_backoff,
    )
    results = downloader.run_bulk_download(
        symbols=_symbols(args.symbols),
        start=args.start,
        end=args.end,
        lookback_days=args.lookback_days,
        force_refresh=args.force_refresh,
        fail_on_error=not args.continue_on_error,
    )
    succeeded = sum(r.success for r in results)
    failed = len(results) - succeeded
    rows = sum(r.rows for r in results if r.success)
    print(
        f"Market ingestion complete: {succeeded} succeeded, "
        f"{failed} failed, {rows} total rows."
    )
    return 0 if failed == 0 or args.continue_on_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
