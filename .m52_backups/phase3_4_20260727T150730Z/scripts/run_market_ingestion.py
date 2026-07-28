from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

DEFAULT_UNIVERSE_FILE = Path("data/universe/us_listed_equities_etfs.csv")
DEFAULT_INDEX_UNIVERSE_FILE = Path("data/universe/us_market_indices.csv")
_SYMBOL_COLUMNS = ("canonical_symbol", "symbol", "provider_symbol", "ticker")
_ACTIVE_VALUES = {"1", "true", "yes", "y", "active"}


def _normalize_symbols(values: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        symbol = str(value or "").strip().upper()
        if not symbol or symbol.startswith("#") or symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    if not out:
        raise ValueError("No valid symbols were resolved for market ingestion.")
    return tuple(out)


def _read_delimited_symbol_file(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(handle, dialect))
    if not rows:
        raise ValueError(f"Symbol file is empty: {path}")
    header = [cell.strip().lower() for cell in rows[0]]
    symbol_index = next((header.index(column) for column in _SYMBOL_COLUMNS if column in header), None)
    active_index = header.index("active") if "active" in header else None
    if symbol_index is not None:
        values: list[str] = []
        for row in rows[1:]:
            if symbol_index >= len(row):
                continue
            if active_index is not None and active_index < len(row):
                active = row[active_index].strip().lower()
                if active and active not in _ACTIVE_VALUES:
                    continue
            values.append(row[symbol_index])
        return _normalize_symbols(values)
    return _normalize_symbols(cell for row in rows for cell in row)


def load_symbols_file(path_value: str | Path) -> tuple[str, ...]:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Symbol file not found: {path}")
    if path.suffix.lower() in {".csv", ".tsv"}:
        return _read_delimited_symbol_file(path)
    tokens: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tokens.extend(part.strip() for part in line.replace("\t", ",").split(","))
    return _normalize_symbols(tokens)


def build_registry(universe_file: str | Path, index_universe_file: str | Path):
    from trading_ai.market.instruments import CanonicalInstrumentRegistry
    return CanonicalInstrumentRegistry.from_files((universe_file, index_universe_file))


def resolve_instruments(
    registry,
    symbols: str | None,
    symbols_file: str | None,
    asset_classes: str | None,
):
    selected_symbols: tuple[str, ...] | None = None
    if symbols:
        selected_symbols = _normalize_symbols(symbols.split(","))
    elif symbols_file:
        selected_symbols = load_symbols_file(symbols_file)
    selected_classes = _normalize_symbols(asset_classes.split(",")) if asset_classes else None
    instruments = registry.select(symbols=selected_symbols, asset_classes=selected_classes)
    if not instruments:
        raise ValueError("No active canonical instruments matched the requested filters.")
    return instruments


def resolve_symbols(symbols, symbols_file, universe_file=DEFAULT_UNIVERSE_FILE):
    """Backward-compatible symbol resolver retained for existing tests and callers."""
    if symbols:
        return _normalize_symbols(symbols.split(","))
    if symbols_file:
        return load_symbols_file(symbols_file)
    return load_symbols_file(universe_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Authoritative market ingestion pipeline: Yahoo equity/ETF OHLCV, "
            "Polygon index OHLC, and Polygon options snapshots."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", help="Canonical symbols only, for example AAPL,SPX,NDX,RUT")
    group.add_argument("--symbols-file", help="File containing canonical symbols")
    parser.add_argument("--universe-file", default=str(DEFAULT_UNIVERSE_FILE))
    parser.add_argument("--index-universe-file", default=str(DEFAULT_INDEX_UNIVERSE_FILE))
    parser.add_argument("--asset-classes", help="Optional comma-separated filter: EQUITY,ETF,INDEX")
    parser.add_argument("--data-scope", choices=["underlying", "options", "all"], default="all")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--lookback-days", type=int, default=730)
    parser.add_argument("--max-workers", type=int, default=4, help="Concurrent equity/ETF OHLCV workers. Default: 4")
    parser.add_argument("--request-interval", type=float, default=1.0, help="Global minimum seconds between Yahoo requests. Default: 1.0")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--initial-backoff", type=float, default=30.0)
    parser.add_argument("--max-backoff", type=float, default=300.0)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--options-minimum-dte", type=int, default=14)
    parser.add_argument("--options-maximum-dte", type=int, default=90)
    parser.add_argument("--options-minimum-open-interest", type=int, default=1)
    parser.add_argument("--options-minimum-volume", type=int, default=0)
    parser.add_argument("--options-maximum-strike-distance-pct", type=float, default=.40)
    parser.add_argument("--polygon-requests-per-second", type=float, default=4.0)
    parser.add_argument("--options-batch-size", type=int, default=5000)
    parser.add_argument("--options-manifest", default="reports/market_ingestion/options_manifest.json")
    parser.add_argument("--options-report", default="reports/market_ingestion/options_latest.json")
    parser.add_argument("--skip-dealer-positioning", action="store_true")
    parser.add_argument("--dealer-positioning-output-dir", default="reports/m44")
    parser.add_argument("--dealer-positioning-report", default="reports/market_ingestion/dealer_positioning_latest.json")
    parser.add_argument("--dealer-positioning-minimum-dte", type=int, default=1)
    parser.add_argument("--dealer-positioning-maximum-dte", type=int, default=365)
    parser.add_argument("--dealer-positioning-maximum-snapshot-age-days", type=int, default=0)
    parser.add_argument("--dealer-sign-convention", choices=["street_proxy", "customer_long_proxy", "unsigned_market_exposure"], default="street_proxy")
    parser.add_argument("--dealer-positioning-write-reports", action="store_true")
    parser.add_argument("--dealer-positioning-fail-fast", action="store_true")
    parser.add_argument("--skip-market-overview", action="store_true")
    return parser


def _run_underlying_ingestion(args: argparse.Namespace, instruments) -> int:
    from trading_ai.market.downloader import MarketDownloader
    from trading_ai.market.providers.polygon_index import PolygonIndexHistoricalProvider

    failed = 0
    equity_symbols = tuple(i.canonical_symbol for i in instruments if i.asset_class in {"EQUITY", "ETF"})
    index_instruments = tuple(i for i in instruments if i.asset_class == "INDEX")

    if equity_symbols:
        results = MarketDownloader(
            max_workers=args.max_workers,
            request_interval_seconds=args.request_interval,
            max_retries=args.max_retries,
            initial_backoff_seconds=args.initial_backoff,
            max_backoff_seconds=args.max_backoff,
        ).run_bulk_download(
            symbols=equity_symbols,
            start=args.start,
            end=args.end,
            lookback_days=args.lookback_days,
            force_refresh=args.force_refresh,
            fail_on_error=not args.continue_on_error,
        )
        failed += sum(not result.success for result in results)

    if index_instruments:
        from trading_ai.database import SessionLocal
        from trading_ai.market.index_ingestion import IndexHistoryIngestionService

        index_provider = PolygonIndexHistoricalProvider(
            {instrument.canonical_symbol: instrument.price_ticker for instrument in index_instruments}
        )
        profile = IndexHistoryIngestionService(
            provider=index_provider,
            session_factory=SessionLocal,
            max_retries=args.max_retries,
            initial_backoff_seconds=args.initial_backoff,
            max_backoff_seconds=args.max_backoff,
        ).run(
            symbols=tuple(i.canonical_symbol for i in index_instruments),
            start=args.start,
            end=args.end,
            lookback_days=args.lookback_days,
            continue_on_error=args.continue_on_error,
        )
        for result in profile.results:
            if result.success:
                print(
                    f"[OK] {result.symbol}: {result.downloaded_rows} downloaded; "
                    f"{result.persisted_rows} persisted "
                    f"({result.inserted_rows} inserted, {result.updated_rows} updated); "
                    f"attempts={result.attempts}"
                )
            else:
                print(
                    f"[FAILED] {result.symbol}: 0 persisted; "
                    f"attempts={result.attempts}; {result.error}"
                )
        failed += profile.failed_count
    return failed


def main(argv=None) -> int:
    from trading_ai.config import settings
    from trading_ai.database import SessionLocal
    from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore, OptionHistoryIngestionService
    from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy
    from trading_ai.scanner.options_market_data_ingestion.serialization import write_ingestion_profile_json

    args = build_parser().parse_args(argv)
    registry = build_registry(args.universe_file, args.index_universe_file)
    instruments = resolve_instruments(registry, args.symbols, args.symbols_file, args.asset_classes)
    symbols = tuple(instrument.canonical_symbol for instrument in instruments)
    counts = Counter(instrument.asset_class for instrument in instruments)

    print(f"Market ingestion universe: {len(symbols)} canonical instruments")
    print("Asset classes: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    for instrument in instruments:
        if instrument.asset_class == "INDEX":
            print(
                f"[INDEX] {instrument.canonical_symbol}: price={instrument.price_ticker}, "
                f"options_snapshot={instrument.options_snapshot_ticker}, "
                f"options_reference={instrument.options_reference_ticker}"
            )
    print(f"OHLCV concurrency: workers={args.max_workers}, request_interval={args.request_interval:.2f}s")

    failed = 0
    if args.data_scope in {"underlying", "all"}:
        failed += _run_underlying_ingestion(args, instruments)

    if args.data_scope in {"options", "all"}:
        api_key = getattr(settings, "polygon_api_key", None)
        if not api_key:
            raise RuntimeError("POLYGON_API_KEY is not configured")
        capture_date = date.fromisoformat((args.end or date.today().isoformat())[:10])
        options_instruments = tuple(instrument for instrument in instruments if instrument.options_eligible)
        options_symbols = tuple(instrument.canonical_symbol for instrument in options_instruments)
        snapshot_tickers = {
            instrument.canonical_symbol: instrument.options_snapshot_ticker
            for instrument in options_instruments
        }
        provider = PolygonOptionChainSnapshotProvider(
            str(api_key),
            as_of_date=capture_date,
            policy=PolygonSnapshotPolicy(
                minimum_dte=args.options_minimum_dte,
                maximum_dte=args.options_maximum_dte,
                minimum_open_interest=args.options_minimum_open_interest,
                minimum_volume=args.options_minimum_volume,
                maximum_strike_distance_pct=args.options_maximum_strike_distance_pct,
                requests_per_second=args.polygon_requests_per_second,
            ),
            symbol_resolver=lambda symbol: snapshot_tickers[symbol.strip().upper()],
        )
        manifest = IngestionManifestStore(args.options_manifest)
        if args.force_refresh:
            manifest.reset()
        session = SessionLocal()
        try:
            profile = OptionHistoryIngestionService(session, provider, manifest_store=manifest).run(
                symbols=options_symbols,
                batch_size=args.options_batch_size,
                resume=not args.force_refresh,
                fail_fast=not args.continue_on_error,
            )
        finally:
            session.close()
        write_ingestion_profile_json(profile, args.options_report)
        failed += profile.failed_batches
        print(
            f"Options ingestion: {profile.valid_records} valid, "
            f"{profile.inserted_records} inserted, {profile.updated_records} updated, "
            f"{profile.failed_batches} failed batches"
        )

        if not args.skip_dealer_positioning:
            from trading_ai.institutional_market_structure.contracts import DealerPositioningPolicy
            from trading_ai.institutional_market_structure.refresh import DealerPositionRefreshOrchestrator, write_refresh_profile

            positioning_policy = DealerPositioningPolicy(
                minimum_dte=args.dealer_positioning_minimum_dte,
                maximum_dte=args.dealer_positioning_maximum_dte,
                maximum_snapshot_age_days=args.dealer_positioning_maximum_snapshot_age_days,
                dealer_sign_convention=args.dealer_sign_convention,
            )
            positioning_profile = DealerPositionRefreshOrchestrator(
                positioning_policy,
                output_dir=Path(args.dealer_positioning_output_dir),
                write_reports=args.dealer_positioning_write_reports,
            ).run(options_symbols, capture_date, continue_on_error=not args.dealer_positioning_fail_fast)
            write_refresh_profile(positioning_profile, args.dealer_positioning_report)
            if args.dealer_positioning_fail_fast:
                failed += positioning_profile.failed_symbols
            print(
                "Dealer positioning refresh: "
                f"{positioning_profile.refreshed_symbols} refreshed, "
                f"{positioning_profile.skipped_symbols} skipped, "
                f"{positioning_profile.failed_symbols} failed"
            )

    if not args.skip_market_overview:
        try:
            from trading_ai.market_overview.service import MarketOverviewService
            overview = MarketOverviewService().build(persist=True)
            print(
                "Market overview refresh: "
                f"bias={overview.market_bias}, health={overview.market_health_score:.1f}, "
                f"breadth={overview.breadth_regime}, regime={overview.trend_regime}"
            )
        except Exception as exc:
            print(f"Market overview refresh warning: {type(exc).__name__}: {exc}")
    return 0 if failed == 0 or args.continue_on_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
