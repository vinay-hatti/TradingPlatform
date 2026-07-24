from __future__ import annotations

import argparse
import csv
import tempfile
from datetime import date, timedelta
from pathlib import Path

from trading_ai.database.session import create_session
from trading_ai.market.universe import get_universe
from trading_ai.scanner.market_data_population import (
    BulkMarketDataPopulationService,
    MarketDataPopulationPolicy,
    YFinanceBulkHistoricalProvider,
)
from trading_ai.scanner.market_data_population.repository import PriceHistoryBulkRepository
from trading_ai.daily_scan_workstation.refresh_governance import evaluate_refresh_governance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed market-data refresh for the Daily Scanner.")
    parser.add_argument("--mode", choices=["cache_only", "refresh_missing", "force_full"], default="refresh_missing")
    parser.add_argument("--universe", default="liquid-us-700")
    parser.add_argument("--symbols")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--minimum-bars", type=int, default=20)
    parser.add_argument("--stale-after-days", type=int, default=1)
    parser.add_argument("--minimum-coverage-pct", type=float, default=98.0)
    parser.add_argument("--maximum-failed-symbols", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--maximum-retry-backoff-seconds", type=float, default=60.0)
    parser.add_argument("--retry-jitter-ratio", type=float, default=0.20)
    parser.add_argument("--rate-limit-cooldown-seconds", type=float, default=15.0)
    parser.add_argument("--circuit-breaker-threshold", type=int, default=3)
    parser.add_argument("--circuit-breaker-cooldown-seconds", type=float, default=30.0)
    parser.add_argument("--batch-size", type=int, default=100)
    degraded = parser.add_mutually_exclusive_group()
    degraded.add_argument("--continue-on-degraded", dest="continue_on_degraded", action="store_true")
    degraded.add_argument("--block-on-degraded", dest="continue_on_degraded", action="store_false")
    parser.set_defaults(continue_on_degraded=True)
    return parser.parse_args()


def symbols_for(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        values = [value.strip().upper().replace("_", ".") for value in args.symbols.split(",") if value.strip()]
    else:
        values = list(get_universe(args.universe))
    values = list(dict.fromkeys(values))
    if not values:
        raise ValueError("No symbols selected")
    return values


def universe_file(symbols: list[str], directory: Path) -> Path:
    path = directory / "selected_universe.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "provider_symbol", "active"])
        writer.writeheader()
        writer.writerows({"symbol": symbol, "provider_symbol": symbol, "active": True} for symbol in symbols)
    return path


def covered_symbols(
    repository: PriceHistoryBulkRepository,
    symbols: list[str],
    minimum_bars: int,
    stale_cutoff: date,
) -> tuple[list[str], list[str]]:
    coverage = repository.coverage(symbols)
    covered: list[str] = []
    excluded: list[str] = []
    for symbol in symbols:
        count, latest = coverage.get(symbol, (0, None))
        if count >= minimum_bars and latest is not None and latest >= stale_cutoff:
            covered.append(symbol)
        else:
            excluded.append(symbol)
    return covered, excluded


def print_result(
    *,
    args: argparse.Namespace,
    requested: int,
    current: int,
    missing: int,
    stale: int,
    attempted: int,
    succeeded: int,
    rows_upserted: int,
    covered: list[str],
    excluded: list[str],
) -> tuple[str, bool]:
    decision = evaluate_refresh_governance(
        requested_symbol_count=requested,
        covered_symbol_count=len(covered),
        minimum_coverage_pct=args.minimum_coverage_pct,
        maximum_failed_symbols=args.maximum_failed_symbols,
        continue_on_degraded=args.continue_on_degraded,
    )
    coverage_pct = decision.coverage_pct
    failure_count = decision.failed_symbol_count
    eligible = decision.eligible_to_continue
    status = decision.status

    print(f"Attempted Symbols                {attempted:>10}")
    print(f"Succeeded Symbols                {succeeded:>10}")
    print(f"Failed Symbols                   {failure_count:>10}")
    print(f"Skipped Fresh Symbols            {current:>10}")
    print(f"Rows Upserted                    {rows_upserted:>10}")
    print(f"Coverage                         {coverage_pct:>9.2f}%")
    print(f"Minimum Required Coverage        {args.minimum_coverage_pct:>9.2f}%")
    print(f"Maximum Failed Symbols           {args.maximum_failed_symbols:>10}")
    print(f"Continue On Degraded             {str(args.continue_on_degraded):>10}")
    print(f"Eligible To Continue             {str(eligible):>10}")
    print(f"Status                           {status:>10}")
    print(f"Covered Symbols                  {len(covered):>10}")
    print(f"Excluded Symbols                 {','.join(excluded) if excluded else 'NONE'}")
    return status, eligible


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start cannot be after end")
    if not 0 <= args.minimum_coverage_pct <= 100:
        raise ValueError("minimum-coverage-pct must be between 0 and 100")
    if args.maximum_failed_symbols < 0:
        raise ValueError("maximum-failed-symbols cannot be negative")

    symbols = symbols_for(args)
    session = create_session()
    try:
        repository = PriceHistoryBulkRepository(session)
        before = repository.coverage(symbols)
        stale_cutoff = end - timedelta(days=args.stale_after_days)
        missing: list[str] = []
        stale: list[str] = []
        current: list[str] = []
        for symbol in symbols:
            count, latest = before.get(symbol, (0, None))
            if latest is None or count < args.minimum_bars:
                missing.append(symbol)
            elif latest < stale_cutoff:
                stale.append(symbol)
            else:
                current.append(symbol)

        print("=========================================================")
        print("Daily Scanner Market Data Refresh")
        print("=========================================================")
        print(f"Refresh Mode                     {args.mode}")
        print(f"Requested Symbols                {len(symbols):>10}")
        print(f"Current Symbols                  {len(current):>10}")
        print(f"Missing Symbols                  {len(missing):>10}")
        print(f"Stale Symbols                    {len(stale):>10}")

        attempted = 0
        succeeded = 0
        rows_upserted = 0
        provider_diagnostics: dict = {}
        if args.mode != "cache_only":
            targets = symbols if args.mode == "force_full" else list(dict.fromkeys(missing + stale))
            if targets:
                with tempfile.TemporaryDirectory(prefix="m43-refresh-") as temp_dir:
                    csv_path = universe_file(targets, Path(temp_dir))
                    policy = MarketDataPopulationPolicy(
                        lookback_days=max(1, (end - start).days),
                        minimum_bars=args.minimum_bars,
                        stale_after_days=args.stale_after_days,
                        minimum_coverage_pct=args.minimum_coverage_pct,
                        batch_size=args.batch_size,
                        max_retries=args.max_retries,
                        retry_backoff_seconds=args.retry_backoff_seconds,
                    )
                    provider = YFinanceBulkHistoricalProvider(
                        cache_dir="data/cache/yfinance",
                        max_retries=args.max_retries,
                        initial_backoff_seconds=args.retry_backoff_seconds,
                        max_backoff_seconds=args.maximum_retry_backoff_seconds,
                        jitter_ratio=args.retry_jitter_ratio,
                        rate_limit_cooldown_seconds=args.rate_limit_cooldown_seconds,
                        circuit_breaker_threshold=args.circuit_breaker_threshold,
                        circuit_breaker_cooldown_seconds=args.circuit_breaker_cooldown_seconds,
                    )
                    # Provider-level retry owns 429 handling; avoid retrying the whole
                    # 100-symbol orchestration batch after each provider chunk has exhausted.
                    policy = MarketDataPopulationPolicy(
                        lookback_days=policy.lookback_days,
                        minimum_bars=policy.minimum_bars,
                        stale_after_days=policy.stale_after_days,
                        minimum_coverage_pct=policy.minimum_coverage_pct,
                        batch_size=policy.batch_size,
                        max_retries=0,
                        retry_backoff_seconds=policy.retry_backoff_seconds,
                        request_pause_seconds=policy.request_pause_seconds,
                        continue_on_error=policy.continue_on_error,
                        minimum_fd_headroom=policy.minimum_fd_headroom,
                        collect_resources_each_batch=policy.collect_resources_each_batch,
                    )
                    result = BulkMarketDataPopulationService(provider, policy).run(
                        session=session,
                        universe_csv=csv_path,
                        report_dir="reports/m43/market_data_refresh",
                        resume=False,
                        force_refresh=True,
                        start=start,
                        end=end,
                    )
                attempted = result.attempted_symbols
                succeeded = result.succeeded_symbols
                rows_upserted = result.rows_upserted
                provider_diagnostics = provider.diagnostics()

        if provider_diagnostics:
            affected = provider_diagnostics.get("affected_symbols", [])
            print("-------------------------------------------")
            print("Provider Health Summary")
            print("-------------------------------------------")
            print(f"Provider                         {provider_diagnostics.get('provider', 'UNKNOWN')}")
            print(f"Provider Status                  {provider_diagnostics.get('status', 'UNKNOWN')}")
            print(f"Provider Requests                {provider_diagnostics.get('requests', 0):>10}")
            print(f"Provider Retries                 {provider_diagnostics.get('retries', 0):>10}")
            print(f"Provider Rate Limits             {provider_diagnostics.get('rate_limit_events', 0):>10}")
            print(f"Provider Circuit Opens           {provider_diagnostics.get('circuit_open_events', 0):>10}")
            print(f"Suppressed Provider Log Lines    {provider_diagnostics.get('suppressed_log_lines', 0):>10}")
            print(f"Provider Affected Symbols        {','.join(affected[:25]) if affected else 'NONE'}")
            if len(affected) > 25:
                print(f"Provider Affected Symbol Count   {len(affected):>10}")

        covered, excluded = covered_symbols(repository, symbols, args.minimum_bars, stale_cutoff)
        _, eligible = print_result(
            args=args,
            requested=len(symbols),
            current=len(current),
            missing=len(missing),
            stale=len(stale),
            attempted=attempted,
            succeeded=succeeded,
            rows_upserted=rows_upserted,
            covered=covered,
            excluded=excluded,
        )
        return 0 if eligible else 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
