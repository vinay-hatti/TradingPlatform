from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from trading_ai.database.session import create_session
from trading_ai.scanner.universe_management import (
    FileUniverseProvider,
    LiquidityGovernancePolicy,
    NasdaqSymbolDirectoryProvider,
)
from trading_ai.scanner.market_data_population import MarketDataPopulationPolicy, YFinanceBulkHistoricalProvider
from trading_ai.scanner.universe_management.liquidity_metrics_builder import LiquidityMetricsBuildPolicy
from trading_ai.scanner.universe_pipeline import UniversePipelinePolicy, UniversePipelineService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete Milestone 35 Phase 1 institutional universe pipeline.")
    parser.add_argument("--nasdaq", action="store_true", help="Provider used only with --rebuild-universe.")
    parser.add_argument("--rebuild-universe", action="store_true", help="Explicitly rebuild and replace the canonical universe CSV. Default behavior preserves the existing canonical CSV.")
    parser.add_argument("--csv", action="append", default=[], metavar="PATH", help="Add a universe CSV provider; repeatable.")
    parser.add_argument("--minimum-symbol-count", type=int, default=6000)
    parser.add_argument("--maximum-source-age-hours", type=int, default=72)
    parser.add_argument("--strict-providers", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--skip-download", "--skip-universe-refresh", dest="skip_universe_refresh", action="store_true")
    parser.add_argument("--skip-liquidity", "--skip-liquidity-metrics", dest="skip_liquidity_metrics", action="store_true")
    parser.add_argument("--use-cache", action="store_true", help="Allow provider cache fallback (enabled by the resilient provider layer).")
    parser.add_argument("--reference-csv")
    parser.add_argument("--quote-csv")
    parser.add_argument("--universe-dir", default="data/universe")
    parser.add_argument("--market-dir", default="data/market")
    parser.add_argument("--report-dir", default="reports/m35/phase1/pipeline")
    parser.add_argument("--minimum-price", type=float, default=5.0)
    parser.add_argument("--minimum-average-volume", type=int, default=200000)
    parser.add_argument("--minimum-dollar-volume", type=float, default=10000000.0)
    parser.add_argument("--maximum-spread-pct", type=float, default=0.05)
    parser.add_argument("--minimum-market-cap", type=float, default=300000000.0)
    parser.add_argument("--minimum-option-volume", type=int, default=0)
    parser.add_argument("--minimum-option-open-interest", type=int, default=0)
    parser.add_argument("--require-options-eligible", action="store_true")
    parser.add_argument("--allow-empty-eligible", action="store_true")
    parser.add_argument("--allow-missing-price-history", action="store_true")
    parser.add_argument("--populate-market-data", action="store_true", help="Populate price_history before liquidity metrics.")
    parser.add_argument("--market-data-lookback-days", type=int, default=90)
    parser.add_argument("--market-data-minimum-bars", type=int, default=20)
    parser.add_argument("--market-data-stale-after-days", type=int, default=7)
    parser.add_argument("--market-data-minimum-coverage-pct", type=float, default=70.0)
    parser.add_argument("--market-data-batch-size", type=int, default=100)
    parser.add_argument("--market-data-max-retries", type=int, default=3)
    parser.add_argument("--market-data-request-pause-seconds", type=float, default=1.0)
    parser.add_argument("--market-data-force-refresh", action="store_true")
    parser.add_argument("--market-data-limit", type=int)
    args = parser.parse_args()

    providers = []
    if args.rebuild_universe:
        if args.nasdaq:
            providers.append(NasdaqSymbolDirectoryProvider())
        providers.extend(FileUniverseProvider(path, name=f"CSV_{index}") for index, path in enumerate(args.csv, 1))
        if not providers:
            parser.error("--rebuild-universe requires --nasdaq or --csv PATH")
    elif args.nasdaq or args.csv:
        parser.error("--nasdaq/--csv would replace the canonical allowlist; add --rebuild-universe only when replacement is intentional")

    universe_dir = Path(args.universe_dir); market_dir = Path(args.market_dir); report_dir = Path(args.report_dir)
    temp = None
    if args.dry_run:
        temp = tempfile.TemporaryDirectory(prefix="m35_phase1_dry_run_")
        root = Path(temp.name)
        universe_dir, market_dir, report_dir = root / "data/universe", root / "data/market", root / "reports/m35/phase1/pipeline"

    policy = UniversePipelinePolicy(
        minimum_symbol_count=args.minimum_symbol_count,
        maximum_source_age_hours=args.maximum_source_age_hours,
        strict_providers=args.strict_providers,
        require_nonempty_eligible_universe=not args.allow_empty_eligible,
    )
    liquidity_policy = LiquidityGovernancePolicy(
        minimum_price=args.minimum_price,
        minimum_average_daily_volume=args.minimum_average_volume,
        minimum_average_daily_dollar_volume=args.minimum_dollar_volume,
        maximum_bid_ask_spread_pct=args.maximum_spread_pct,
        minimum_market_cap=args.minimum_market_cap,
        minimum_option_volume=args.minimum_option_volume,
        minimum_option_open_interest=args.minimum_option_open_interest,
        require_options_eligible=args.require_options_eligible,
    )
    metrics_policy = LiquidityMetricsBuildPolicy(require_price_history=not args.allow_missing_price_history)
    market_data_policy = MarketDataPopulationPolicy(
        lookback_days=args.market_data_lookback_days,
        minimum_bars=args.market_data_minimum_bars,
        stale_after_days=args.market_data_stale_after_days,
        minimum_coverage_pct=args.market_data_minimum_coverage_pct,
        batch_size=args.market_data_batch_size,
        max_retries=args.market_data_max_retries,
        request_pause_seconds=args.market_data_request_pause_seconds,
    )

    session = None
    try:
        if not args.report_only and not args.skip_liquidity_metrics:
            session = create_session()
        result = UniversePipelineService(policy).run(
            providers=providers, session=session, universe_dir=universe_dir, market_dir=market_dir, report_dir=report_dir,
            reference_csv=args.reference_csv, quote_csv=args.quote_csv, resume=args.resume, dry_run=args.dry_run,
            report_only=args.report_only, skip_universe_refresh=(args.skip_universe_refresh or not args.rebuild_universe),
            skip_liquidity_metrics=args.skip_liquidity_metrics, liquidity_policy=liquidity_policy, metrics_policy=metrics_policy,
            populate_market_data=args.populate_market_data,
            market_data_provider=YFinanceBulkHistoricalProvider() if args.populate_market_data else None,
            market_data_policy=market_data_policy,
            market_data_resume=args.resume,
            market_data_force_refresh=args.market_data_force_refresh,
            market_data_limit=args.market_data_limit,
        )
    finally:
        if session is not None:
            session.close()

    print("=========================================================")
    print("Institutional Market Universe Refresh")
    print("=========================================================")
    for item in result.stage_results:
        print(f"{item.stage:<32} {item.status:>10}  {item.elapsed_seconds:8.3f}s")
    print(f"Universe Symbols                 {result.universe_count:>10}")
    print(f"Liquidity Metrics                {result.metrics_count:>10}")
    print(f"Eligible Symbols                 {result.eligible_count:>10}")
    print(f"Rejected Symbols                 {result.rejected_count:>10}")
    print(f"Review Symbols                   {result.review_count:>10}")
    print(f"Elapsed Time                     {result.elapsed_seconds:>9.3f}s")
    print(f"Pipeline Status                  {result.status:>10}")
    print(f"Reports                          {report_dir}")
    if result.error:
        print(f"ERROR: {result.error}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if temp is not None:
        print(f"Dry-run output                   {temp.name}")
        temp.cleanup()
    if result.status == "FAILED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
