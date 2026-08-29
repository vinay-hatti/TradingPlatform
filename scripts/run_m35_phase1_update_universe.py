from __future__ import annotations

import argparse

from trading_ai.scanner.universe_management import (
    AutomaticUniverseBuilderService,
    FileUniverseProvider,
    NasdaqSymbolDirectoryProvider,
    UniverseRefreshPolicy,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and atomically publish the canonical U.S. listed equity and ETF universe.")
    parser.add_argument("--nasdaq", action="store_true", help="Use Nasdaq Symbol Directory feeds.")
    parser.add_argument("--csv", action="append", default=[], metavar="PATH", help="Add a CSV provider; repeatable.")
    parser.add_argument("--minimum-symbol-count", type=int, default=6000)
    parser.add_argument("--maximum-source-age-hours", type=int, default=72)
    parser.add_argument("--output-dir", default="data/universe")
    parser.add_argument("--report-dir", default="reports/m35/phase1/universe_refresh")
    parser.add_argument("--strict-providers", action="store_true", help="Reject publication if any provider is failed or stale.")
    args = parser.parse_args()
    providers = []
    if args.nasdaq:
        providers.append(NasdaqSymbolDirectoryProvider())
    providers.extend(FileUniverseProvider(path, name=f"CSV_{index}") for index, path in enumerate(args.csv, 1))
    if not providers:
        parser.error("At least one provider is required: --nasdaq or --csv PATH")
    policy = UniverseRefreshPolicy(
        minimum_symbol_count=args.minimum_symbol_count,
        maximum_source_age_hours=args.maximum_source_age_hours,
        allow_degraded_publish=not args.strict_providers,
    )
    result = AutomaticUniverseBuilderService(policy).refresh(providers, output_dir=args.output_dir, report_dir=args.report_dir)
    print("========== Automatic Universe Refresh ==========")
    print(f"Status           : {result.status}")
    print(f"Published        : {result.published}")
    print(f"Symbols          : {result.symbol_count}")
    print(f"Added            : {result.added_count}")
    print(f"Removed          : {result.removed_count}")
    print(f"Unchanged        : {result.unchanged_count}")
    print(f"Failed providers : {result.failed_provider_count}")
    print(f"Stale providers  : {result.stale_provider_count}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if not result.published:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
