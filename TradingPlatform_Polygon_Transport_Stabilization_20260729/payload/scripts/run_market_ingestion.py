from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from collections import Counter
from datetime import date, datetime, timezone
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
            "Authoritative Polygon-only market ingestion pipeline: equity/ETF OHLCV, "
            "index OHLC, option chains, and option quotes."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", help="Canonical symbols only, for example AAPL,SPX,NDX,RUT")
    group.add_argument("--symbols-file", help="File containing canonical symbols")
    parser.add_argument("--universe-file", default=str(DEFAULT_UNIVERSE_FILE))
    parser.add_argument("--index-universe-file", default=str(DEFAULT_INDEX_UNIVERSE_FILE))
    parser.add_argument("--asset-classes", help="Optional comma-separated filter: EQUITY,ETF,INDEX")
    parser.add_argument(
        "--mode",
        choices=["daily", "intraday", "analytics", "recovery"],
        default="daily",
        help=(
            "Operational preset. daily=incremental underlying + fresh options; "
            "intraday=fresh options only; analytics=reuse options and rebuild analytics; "
            "recovery=force all stages. Explicit low-level flags remain supported."
        ),
    )
    parser.add_argument("--data-scope", choices=["underlying", "options", "all"], default=None)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--lookback-days", type=int, default=730)
    parser.add_argument("--max-workers", type=int, default=4, help="Concurrent equity/ETF OHLCV workers. Default: 4")
    parser.add_argument("--request-interval", type=float, default=1.0, help="Global minimum seconds between Polygon equity/ETF requests. Default: 1.0")
    parser.add_argument("--polygon-connect-timeout", type=float, default=5.0, help="Polygon equity/ETF connection timeout in seconds. Default: 5.0")
    parser.add_argument("--polygon-read-timeout", type=float, default=30.0, help="Polygon equity/ETF read timeout in seconds. Default: 30.0")
    parser.add_argument("--polygon-sdk-retries", type=int, default=0, help="Retries inside the Polygon SDK. Default: 0 so paced application retries remain authoritative.")
    parser.add_argument("--polygon-pools-per-worker", type=int, default=1, help="urllib3 pools per worker-local Polygon client. Default: 1")
    parser.add_argument("--network-backoff", type=float, default=5.0, help="Initial backoff for connection/timeout failures. Default: 5.0")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--initial-backoff", type=float, default=30.0)
    parser.add_argument("--max-backoff", type=float, default=300.0)
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help=(
            "Legacy compatibility alias that forces underlying, options, dealer-positioning, "
            "and Market Overview refreshes. Prefer the stage-specific force flags."
        ),
    )
    parser.add_argument(
        "--force-underlying-refresh",
        action="store_true",
        help="Re-fetch the requested Polygon underlying history without incremental reuse.",
    )
    parser.add_argument(
        "--force-options-refresh",
        action="store_true",
        help="Reset the options manifest and rebuild the requested Polygon option snapshot batches.",
    )
    parser.add_argument(
        "--reuse-options-snapshot",
        action="store_true",
        help=(
            "Skip Polygon option requests and reuse the latest persisted option snapshot. "
            "Fresh Polygon options are the default for data-scope options/all."
        ),
    )
    parser.add_argument(
        "--options-snapshot-run-id",
        default=None,
        help="Optional cycle id used to resume an interrupted fresh option snapshot run.",
    )
    parser.add_argument(
        "--maximum-reused-options-age-minutes",
        type=int,
        default=None,
        help=(
            "Maximum permitted age for --reuse-options-snapshot. Defaults to 60 minutes "
            "during regular US market hours and 4320 minutes outside market hours."
        ),
    )
    parser.add_argument(
        "--options-lock-file",
        default="reports/market_ingestion/options_ingestion.lock",
        help="Process lock preventing overlapping Polygon option snapshot runs.",
    )
    parser.add_argument(
        "--force-dealer-refresh",
        action="store_true",
        help="Recompute dealer-positioning snapshots even when current-date derived rows already exist.",
    )
    parser.add_argument(
        "--force-market-overview-refresh",
        action="store_true",
        help="Rebuild Market Overview even when its persisted source lineage is already current.",
    )
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
    parser.add_argument("--lifecycle-report", default="reports/market_ingestion/lifecycle_latest.json")
    parser.add_argument("--skip-dealer-positioning", action="store_true")
    parser.add_argument("--dealer-positioning-output-dir", default="reports/m44")
    parser.add_argument("--dealer-positioning-report", default="reports/market_ingestion/dealer_positioning_latest.json")
    parser.add_argument("--dealer-positioning-minimum-dte", type=int, default=1)
    parser.add_argument("--dealer-positioning-maximum-dte", type=int, default=365)
    parser.add_argument("--dealer-positioning-maximum-snapshot-age-days", type=int, default=0)
    parser.add_argument("--dealer-sign-convention", choices=["street_proxy", "customer_long_proxy", "unsigned_market_exposure"], default="street_proxy")
    parser.add_argument("--dealer-positioning-write-reports", action="store_true")
    parser.add_argument("--dealer-positioning-fail-fast", action="store_true")
    parser.add_argument(
        "--skip-trend-intelligence",
        action="store_true",
        help="Skip Milestone 52 trend state, transition, forecast, institutional and platform-context stages.",
    )
    parser.add_argument(
        "--force-trend-refresh",
        action="store_true",
        help="Force execution of all Milestone 52 trend stages even when only reused market data is requested.",
    )
    parser.add_argument(
        "--trend-platform-report",
        default="reports/trend_intelligence/platform_integration_latest.json",
        help="Unified Trend Intelligence platform-context report path.",
    )
    parser.add_argument("--skip-market-overview", action="store_true")
    parser.add_argument(
        "--skip-market-intelligence",
        action="store_true",
        help="Skip the derived Market Intelligence rebuild. This also prevents automatic publication.",
    )
    parser.add_argument(
        "--skip-publication",
        action="store_true",
        help="Do not evaluate and publish the governed scanner-ready market state.",
    )
    parser.add_argument("--publication-name", default="current_market_state")
    parser.add_argument(
        "--publication-run-id",
        default=None,
        help="Optional publication run id. A UTC ingestion id is generated when omitted.",
    )
    return parser


def _run_underlying_ingestion(args: argparse.Namespace, instruments) -> int:
    from trading_ai.config import settings
    from trading_ai.database import SessionLocal
    from trading_ai.market.downloader import MarketDownloader
    from trading_ai.market.index_ingestion import IndexHistoryIngestionService
    from trading_ai.market.providers.polygon import PolygonHistoricalProvider
    from trading_ai.market.providers.polygon_index import PolygonIndexHistoricalProvider
    from trading_ai.market.service import MarketService

    api_key = getattr(settings, "polygon_api_key", None)
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is not configured")

    failed = 0
    equity_instruments = tuple(
        instrument for instrument in instruments
        if instrument.asset_class in {"EQUITY", "ETF"}
    )
    index_instruments = tuple(
        instrument for instrument in instruments
        if instrument.asset_class == "INDEX"
    )

    if equity_instruments:
        equity_provider = PolygonHistoricalProvider(
            {
                instrument.canonical_symbol: instrument.price_ticker
                for instrument in equity_instruments
            },
            api_key=str(api_key),
            connect_timeout_seconds=args.polygon_connect_timeout,
            read_timeout_seconds=args.polygon_read_timeout,
            sdk_retries=args.polygon_sdk_retries,
            pools_per_worker=args.polygon_pools_per_worker,
        )
        equity_service = MarketService(
            provider=equity_provider,
            cache_dir=".cache/market/polygon",
            session_factory=SessionLocal,
        )
        results = MarketDownloader(
            service=equity_service,
            max_workers=args.max_workers,
            request_interval_seconds=args.request_interval,
            max_retries=args.max_retries,
            initial_backoff_seconds=args.initial_backoff,
            network_backoff_seconds=args.network_backoff,
            max_backoff_seconds=args.max_backoff,
        ).run_bulk_download(
            symbols=tuple(i.canonical_symbol for i in equity_instruments),
            start=args.start,
            end=args.end,
            lookback_days=args.lookback_days,
            force_refresh=args.force_underlying_refresh,
            fail_on_error=not args.continue_on_error,
        )
        failed += sum(not result.success for result in results)

    if index_instruments:
        index_provider = PolygonIndexHistoricalProvider(
            {
                instrument.canonical_symbol: instrument.price_ticker
                for instrument in index_instruments
            },
            api_key=str(api_key),
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
                    f"provider=PolygonIndexHistoricalProvider; attempts={result.attempts}"
                )
            else:
                print(
                    f"[FAILED] {result.symbol}: 0 persisted; "
                    f"attempts={result.attempts}; {result.error}"
                )
        failed += profile.failed_count
    return failed


def _apply_mode_preset(args: argparse.Namespace) -> argparse.Namespace:
    """Resolve simple operational modes while preserving explicit advanced controls."""
    mode = args.mode or "daily"
    if args.data_scope is None:
        args.data_scope = {
            "daily": "all",
            "intraday": "options",
            "analytics": "all",
            "recovery": "all",
        }[mode]
    if mode == "analytics":
        args.reuse_options_snapshot = True
    elif mode == "recovery":
        args.force_refresh = True
    return args


def _write_lifecycle_report(args: argparse.Namespace, *, started_at: datetime, completed_at: datetime,
                            failed: int, post_ingestion_failed: bool, underlying_refreshed: bool,
                            options_refreshed: bool, dealer_refreshed: bool, trend_refreshed: bool, publication) -> None:
    path = Path(args.lifecycle_report)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": args.mode,
        "data_scope": args.data_scope,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
        "status": "FAILED" if post_ingestion_failed else ("DEGRADED" if failed else "READY"),
        "stages": {
            "underlying": {"requested": args.data_scope in {"underlying", "all"}, "refreshed": underlying_refreshed},
            "options": {"requested": args.data_scope in {"options", "all"}, "mode": "REUSED" if args.reuse_options_snapshot else ("FORCE_REBUILD" if args.force_options_refresh else "FRESH"), "refreshed": options_refreshed},
            "dealer_positioning": {"skipped": args.skip_dealer_positioning, "refreshed": dealer_refreshed},
            "trend_intelligence": {"skipped": args.skip_trend_intelligence, "refreshed": trend_refreshed},
            "market_overview": {"skipped": args.skip_market_overview},
            "market_intelligence": {"skipped": args.skip_market_intelligence},
            "publication": {
                "skipped": args.skip_publication,
                "scanner_ready": None if publication is None else bool(publication.scanner_ready),
                "decision_context_ready": None if publication is None else bool(publication.decision_context_ready),
            },
        },
        "failed_ingestion_units": failed,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    print(f"Ingestion lifecycle report: {path}")


def _validate_option_controls(args: argparse.Namespace) -> argparse.Namespace:
    if args.reuse_options_snapshot and args.force_options_refresh:
        raise ValueError("--reuse-options-snapshot cannot be combined with --force-options-refresh")
    if args.reuse_options_snapshot and args.options_snapshot_run_id:
        raise ValueError("--reuse-options-snapshot cannot be combined with --options-snapshot-run-id")
    if args.maximum_reused_options_age_minutes is not None and args.maximum_reused_options_age_minutes < 0:
        raise ValueError("--maximum-reused-options-age-minutes must be zero or greater")
    return args


def _default_reuse_age_minutes(now: datetime | None = None) -> int:
    from zoneinfo import ZoneInfo
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/Chicago"))
    minutes = local.hour * 60 + local.minute
    regular_session = local.weekday() < 5 and (8 * 60 + 30) <= minutes <= 15 * 60
    return 60 if regular_session else 4320


@contextmanager
def _exclusive_file_lock(path_value: str | Path):
    """Prevent overlapping option snapshots on macOS/Linux using an advisory lock."""
    import fcntl

    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Another options ingestion process already holds lock: {path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _latest_persisted_option_date(session):
    from sqlalchemy import text
    return session.execute(text("SELECT max(quote_date) FROM option_contract_history")).scalar_one_or_none()


def _reuse_options_snapshot(args: argparse.Namespace, manifest) -> tuple[date, str]:
    from trading_ai.database import SessionLocal

    latest_cycle = manifest.latest_cycle() or {}
    completed_at_raw = latest_cycle.get("completed_at")
    cycle_metadata = latest_cycle.get("metadata", {}) if isinstance(latest_cycle.get("metadata"), dict) else {}
    if cycle_metadata.get("completed_successfully") is False:
        raise RuntimeError(
            "The latest option snapshot cycle did not complete successfully and cannot be reused. "
            "Run without --reuse-options-snapshot."
        )
    if not completed_at_raw:
        raise RuntimeError(
            "No completed option snapshot cycle is available for reuse. Run without "
            "--reuse-options-snapshot to fetch a fresh Polygon snapshot."
        )
    completed_at = datetime.fromisoformat(str(completed_at_raw).replace("Z", "+00:00"))
    age_minutes = max(0.0, (datetime.now(timezone.utc) - completed_at.astimezone(timezone.utc)).total_seconds() / 60.0)
    maximum_age = args.maximum_reused_options_age_minutes
    if maximum_age is None:
        maximum_age = _default_reuse_age_minutes()
    if maximum_age and age_minutes > maximum_age:
        raise RuntimeError(
            f"Persisted option snapshot is too old to reuse: age={age_minutes:.1f} minutes, "
            f"maximum={maximum_age} minutes. Run without --reuse-options-snapshot."
        )
    with SessionLocal() as session:
        quote_date = _latest_persisted_option_date(session)
    if quote_date is None:
        raise RuntimeError("option_contract_history is empty; a Polygon snapshot cannot be reused")
    cycle_id = str(latest_cycle.get("cycle_id") or "unknown")
    print(
        "Options snapshot mode: REUSED; "
        f"cycle={cycle_id}; quote_date={quote_date}; age_minutes={age_minutes:.1f}; Polygon requests=0"
    )
    return quote_date, cycle_id


def _resolve_force_controls(args: argparse.Namespace) -> argparse.Namespace:
    """Resolve the legacy global force flag into explicit stage controls."""
    if args.force_refresh:
        args.force_underlying_refresh = True
        args.force_options_refresh = True
        args.force_dealer_refresh = True
        args.force_market_overview_refresh = True
        args.force_trend_refresh = True
    return args


def _current_dealer_symbols(session, symbols: tuple[str, ...], as_of: date) -> set[str]:
    """Return symbols already carrying a dealer snapshot for the requested valuation date."""
    if not symbols:
        return set()
    from sqlalchemy import text

    try:
        rows = session.execute(
            text(
                """
                SELECT DISTINCT upper(symbol) AS symbol
                FROM dealer_position_snapshot
                WHERE as_of_date = :as_of
                  AND upper(symbol) = ANY(:symbols)
                """
            ),
            {"as_of": as_of, "symbols": list(symbols)},
        ).scalars().all()
        return {str(symbol).strip().upper() for symbol in rows if symbol}
    except Exception:
        session.rollback()
        return set()


def _market_overview_is_current(session) -> bool:
    """Check persisted Market Overview lineage against the latest database source dates."""
    from sqlalchemy import text

    try:
        overview = session.execute(
            text(
                """
                SELECT as_of_date, payload_json
                FROM market_overview_snapshot
                ORDER BY snapshot_timestamp DESC
                LIMIT 1
                """
            )
        ).mappings().one_or_none()
        if not overview:
            return False

        latest_price_date = session.execute(text("SELECT max(date) FROM price_history")).scalar_one_or_none()
        latest_dealer_date = session.execute(text("SELECT max(as_of_date) FROM dealer_position_snapshot")).scalar_one_or_none()
        if latest_price_date and overview["as_of_date"] < latest_price_date:
            return False

        payload = overview.get("payload_json")
        if isinstance(payload, str):
            import json
            payload = json.loads(payload)
        lineage = (payload or {}).get("data_lineage", {}) if isinstance(payload, dict) else {}
        persisted_dealer_date = lineage.get("dealer_snapshot_as_of")
        if latest_dealer_date and str(persisted_dealer_date or "") < str(latest_dealer_date):
            return False
        return True
    except Exception:
        session.rollback()
        return False


def _publish_fresh_option_lineage(
    *,
    symbols: tuple[str, ...],
    capture_date: date,
    snapshot_id: str,
    snapshot_timestamp: datetime,
) -> dict[str, object]:
    """Publish the fresh Polygon cycle into the governed timestamped snapshot tables.

    The Daily Scanner reads ``option_contract_history`` for contract selection, while
    scanner-readiness lineage is sourced from ``option_snapshot_run`` and its derived
    option, volatility, and liquidity tables. Both representations must advance as one
    atomic ingestion lifecycle before downstream publication is allowed.
    """
    from trading_ai.database import SessionLocal
    from trading_ai.market_intelligence.ingestion_orchestrator import (
        PolygonDerivedSnapshotPublisher,
    )

    with SessionLocal() as session:
        publisher = PolygonDerivedSnapshotPublisher(session)
        option_result = publisher.publish_option_snapshot(
            symbols=symbols,
            capture_date=capture_date,
            snapshot_timestamp=snapshot_timestamp,
            snapshot_id=snapshot_id,
        )
        if int(option_result.get("rows_written", 0) or 0) <= 0:
            raise RuntimeError(
                "Fresh Polygon ingestion produced no governed option snapshot rows; "
                "downstream publication is blocked to prevent stale lineage."
            )
        volatility_result = publisher.build_volatility_snapshots(
            snapshot_id=snapshot_id,
            capture_date=capture_date,
        )
        liquidity_result = publisher.build_liquidity_snapshots(
            snapshot_id=snapshot_id,
            capture_date=capture_date,
        )

    volatility_rows = int(volatility_result.get("rows_written", 0) or 0)
    liquidity_rows = int(liquidity_result.get("rows_written", 0) or 0)
    if volatility_rows <= 0 or liquidity_rows <= 0:
        raise RuntimeError(
            "Fresh option lineage is incomplete: "
            f"volatility_rows={volatility_rows}, liquidity_rows={liquidity_rows}. "
            "Downstream publication is blocked."
        )

    result = {
        "snapshot_id": str(option_result.get("snapshot_id") or snapshot_id),
        "snapshot_timestamp": str(
            option_result.get("snapshot_timestamp") or snapshot_timestamp.isoformat()
        ),
        "option_rows": int(option_result.get("rows_written", 0) or 0),
        "volatility_rows": volatility_rows,
        "liquidity_rows": liquidity_rows,
        "completeness_score": option_result.get("completeness_score"),
        "status": option_result.get("status", "READY"),
    }
    print(
        "Governed option lineage: "
        f"snapshot={result['snapshot_id']}, timestamp={result['snapshot_timestamp']}, "
        f"contracts={result['option_rows']}, volatility={volatility_rows}, "
        f"liquidity={liquidity_rows}, completeness={result['completeness_score']}"
    )
    return result


def _run_dealer_positioning(args: argparse.Namespace, symbols: tuple[str, ...], capture_date: date) -> tuple[int, bool]:
    """Incrementally refresh missing dealer rows, or rebuild all rows when forced."""
    from trading_ai.database import SessionLocal
    from trading_ai.institutional_market_structure.contracts import DealerPositioningPolicy
    from trading_ai.institutional_market_structure.refresh import DealerPositionRefreshOrchestrator, write_refresh_profile

    requested = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    if not requested:
        print("Dealer positioning refresh: no options-eligible symbols selected")
        return 0, False

    session = SessionLocal()
    try:
        current = set() if args.force_dealer_refresh else _current_dealer_symbols(session, requested, capture_date)
    finally:
        session.close()
    refresh_symbols = requested if args.force_dealer_refresh else tuple(symbol for symbol in requested if symbol not in current)

    if not refresh_symbols:
        print(
            "Dealer positioning refresh: reused "
            f"{len(current)} current snapshots for {capture_date.isoformat()}"
        )
        return 0, False

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
    ).run(refresh_symbols, capture_date, continue_on_error=not args.dealer_positioning_fail_fast)
    write_refresh_profile(positioning_profile, args.dealer_positioning_report)
    print(
        "Dealer positioning refresh: "
        f"{positioning_profile.refreshed_symbols} refreshed, "
        f"{positioning_profile.skipped_symbols} skipped, "
        f"{positioning_profile.failed_symbols} failed, "
        f"{len(current)} reused"
    )
    failed = positioning_profile.failed_symbols if args.dealer_positioning_fail_fast else 0
    return failed, positioning_profile.refreshed_symbols > 0



def _run_command_stage(name: str, command: list[str]) -> None:
    print(f"Trend Intelligence stage: {name}")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {completed.returncode}")


def _run_trend_intelligence_pipeline(args: argparse.Namespace, symbols: tuple[str, ...]) -> bool:
    """Compute and persist all Milestone 52 analytics from database-backed OHLCV.

    Standalone scripts remain diagnostic entry points; this orchestrator is the normal
    operational path and deliberately performs no provider requests itself.
    """
    if args.skip_trend_intelligence:
        print("Trend Intelligence refresh: skipped")
        return False

    symbol_args: list[str] = []
    if args.symbols or args.symbols_file:
        symbol_args.extend(["--symbols", ",".join(symbols)])

    effective_end = args.end or date.today().isoformat()
    dated_args: list[str] = [*symbol_args]
    if args.start:
        dated_args.extend(["--start", args.start])
    dated_args.extend(["--end", effective_end])

    # Each standalone phase has its own CLI contract. Phases 1 and 2 do not
    # accept date arguments; Phases 3 and 4 do. Keep orchestration explicit so
    # future parser changes are caught by the contract regression test.
    stages = (
        ("trend state", "scripts/run_trend_intelligence.py", symbol_args),
        ("trend transitions", "scripts/run_trend_transition_intelligence.py", symbol_args),
        ("trend forecasts", "scripts/run_trend_forecasting.py", dated_args),
        ("institutional participation", "scripts/run_institutional_trend_intelligence.py", dated_args),
    )
    for name, script, stage_args in stages:
        _run_command_stage(name, [sys.executable, script, *stage_args])

    integration_command = [
        sys.executable,
        "scripts/run_trend_platform_integration.py",
        "--symbols",
        ",".join(symbols),
        "--output",
        args.trend_platform_report,
    ]
    _run_command_stage("platform context", integration_command)
    print("Trend Intelligence refresh: READY")
    return True

def _run_market_overview(args: argparse.Namespace, *, upstream_refreshed: bool) -> bool:
    """Build Market Overview only when source lineage changed, unless explicitly forced."""
    from trading_ai.database import SessionLocal
    from trading_ai.market_overview.service import MarketOverviewService

    force = bool(args.force_market_overview_refresh or upstream_refreshed)
    session = SessionLocal()
    try:
        current = False if force else _market_overview_is_current(session)
    finally:
        session.close()
    if current:
        print("Market overview refresh: reused current persisted snapshot")
        return False

    overview = MarketOverviewService().build(persist=True)
    print(
        "Market overview refresh: "
        f"bias={overview.market_bias}, health={overview.market_health_score:.1f}, "
        f"breadth={overview.breadth_regime}, regime={overview.trend_regime}"
    )
    return True


def _run_market_intelligence(args: argparse.Namespace) -> bool:
    """Rebuild the database-backed Market Intelligence snapshot after source analytics."""
    if args.skip_market_intelligence:
        print("Market intelligence refresh: skipped")
        return False
    from trading_ai.market_intelligence.service import MarketIntelligenceService

    snapshot = MarketIntelligenceService().build(persist=True)
    print(
        "Market intelligence refresh: "
        f"correlation={snapshot.correlation.get('regime')}, "
        f"sentiment={snapshot.sentiment.get('sentiment_label')}, "
        f"risk={snapshot.risk.get('risk_regime')}"
    )
    return True


def _publish_scanner_state(args: argparse.Namespace):
    """Evaluate and atomically publish the coherent state consumed by Daily Scanner."""
    if args.skip_publication:
        print("Published market state: skipped")
        return None
    if args.skip_market_intelligence:
        raise RuntimeError(
            "Automatic publication requires Market Intelligence. "
            "Remove --skip-market-intelligence or also pass --skip-publication."
        )

    from trading_ai.database import SessionLocal
    from trading_ai.market_intelligence.publication import ScannerReadinessService

    run_id = args.publication_run_id or (
        "market-ingestion-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    with SessionLocal() as session:
        result = ScannerReadinessService(session).publish(
            run_id=run_id,
            publication_name=args.publication_name,
        )
    print(
        "Published market state: "
        f"status={result.status}, scanner_ready={str(result.scanner_ready).lower()}, "
        f"decision_context_ready={str(result.decision_context_ready).lower()}, "
        f"publication={args.publication_name}, run_id={run_id}"
    )
    return result

def main(argv=None) -> int:
    from trading_ai.config import settings
    from trading_ai.database import SessionLocal
    from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore, OptionHistoryIngestionService
    from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy
    from trading_ai.scanner.options_market_data_ingestion.serialization import write_ingestion_profile_json

    lifecycle_started_at = datetime.now(timezone.utc)
    args = _validate_option_controls(_resolve_force_controls(_apply_mode_preset(build_parser().parse_args(argv))))
    print(f"Ingestion mode: {args.mode}; data_scope={args.data_scope}")
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
    print(
        "Polygon equity/ETF transport: "
        f"thread_local_clients=true, connect_timeout={args.polygon_connect_timeout:.1f}s, "
        f"read_timeout={args.polygon_read_timeout:.1f}s, "
        f"sdk_retries={args.polygon_sdk_retries}, "
        f"pools_per_worker={args.polygon_pools_per_worker}, "
        f"network_backoff={args.network_backoff:.1f}s"
    )

    failed = 0
    underlying_refreshed = False
    options_refreshed = False
    dealer_refreshed = False
    trend_refreshed = False
    if args.data_scope in {"underlying", "all"}:
        failed += _run_underlying_ingestion(args, instruments)
        underlying_refreshed = True

    if args.data_scope in {"options", "all"}:
        capture_date = date.fromisoformat((args.end or date.today().isoformat())[:10])
        options_instruments = tuple(instrument for instrument in instruments if instrument.options_eligible)
        options_symbols = tuple(instrument.canonical_symbol for instrument in options_instruments)
        manifest = IngestionManifestStore(args.options_manifest)

        if args.reuse_options_snapshot:
            _reuse_options_snapshot(args, manifest)
        else:
            api_key = getattr(settings, "polygon_api_key", None)
            if not api_key:
                raise RuntimeError("POLYGON_API_KEY is not configured")
            snapshot_tickers = {
                instrument.canonical_symbol: instrument.options_snapshot_ticker
                for instrument in options_instruments
            }
            cycle_id = args.options_snapshot_run_id or (
                "options-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            )
            mode = "FORCE_REBUILD" if args.force_options_refresh else "FRESH"
            if args.force_options_refresh:
                manifest.reset()
            manifest.begin_cycle(
                cycle_id,
                metadata={
                    "mode": mode,
                    "capture_date": capture_date.isoformat(),
                    "minimum_dte": args.options_minimum_dte,
                    "maximum_dte": args.options_maximum_dte,
                    "symbol_count": len(options_symbols),
                },
            )
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
            with _exclusive_file_lock(args.options_lock_file):
                session = SessionLocal()
                try:
                    profile = OptionHistoryIngestionService(session, provider, manifest_store=manifest).run(
                        symbols=options_symbols,
                        batch_size=args.options_batch_size,
                        resume=True,
                        fail_fast=not args.continue_on_error,
                        manifest_cycle_id=cycle_id,
                    )
                finally:
                    session.close()
            lineage_result: dict[str, object] | None = None
            if profile.failed_batches == 0 and profile.valid_records > 0:
                lineage_result = _publish_fresh_option_lineage(
                    symbols=options_symbols,
                    capture_date=capture_date,
                    snapshot_id=cycle_id,
                    snapshot_timestamp=datetime.fromisoformat(profile.completed_at),
                )
            manifest.complete_cycle(
                cycle_id,
                metadata={
                    "valid_records": profile.valid_records,
                    "inserted_records": profile.inserted_records,
                    "updated_records": profile.updated_records,
                    "failed_batches": profile.failed_batches,
                    "completed_successfully": profile.failed_batches == 0 and lineage_result is not None,
                    "governed_snapshot_id": (lineage_result or {}).get("snapshot_id"),
                    "governed_snapshot_timestamp": (lineage_result or {}).get("snapshot_timestamp"),
                    "governed_option_rows": (lineage_result or {}).get("option_rows", 0),
                    "governed_volatility_rows": (lineage_result or {}).get("volatility_rows", 0),
                    "governed_liquidity_rows": (lineage_result or {}).get("liquidity_rows", 0),
                },
            )
            write_ingestion_profile_json(profile, args.options_report)
            failed += profile.failed_batches
            options_refreshed = profile.failed_batches == 0 and lineage_result is not None
            print(
                f"Options snapshot mode: {mode}; cycle={cycle_id}; "
                f"capture_window={profile.started_at}..{profile.completed_at}"
            )
            print(
                f"Options ingestion: {profile.valid_records} valid, "
                f"{profile.inserted_records} persisted/upserted, "
                f"{profile.failed_batches} failed batches, {profile.resumed_batches} resumed batches"
            )

        if not args.skip_dealer_positioning:
            # A fresh Polygon snapshot always invalidates same-date dealer analytics.
            original_force_dealer = args.force_dealer_refresh
            if options_refreshed:
                args.force_dealer_refresh = True
            dealer_failed, dealer_refreshed = _run_dealer_positioning(args, options_symbols, capture_date)
            args.force_dealer_refresh = original_force_dealer
            failed += dealer_failed

    if args.data_scope == "underlying" and args.force_dealer_refresh and not args.skip_dealer_positioning:
        capture_date = date.fromisoformat((args.end or date.today().isoformat())[:10])
        options_symbols = tuple(
            instrument.canonical_symbol for instrument in instruments if instrument.options_eligible
        )
        dealer_failed, dealer_refreshed = _run_dealer_positioning(args, options_symbols, capture_date)
        failed += dealer_failed

    post_ingestion_failed = False
    try:
        trend_refreshed = _run_trend_intelligence_pipeline(args, symbols)
    except Exception as exc:
        post_ingestion_failed = True
        print(f"Trend Intelligence refresh failed: {type(exc).__name__}: {exc}")

    if not post_ingestion_failed and not args.skip_market_overview:
        try:
            _run_market_overview(
                args,
                upstream_refreshed=bool(underlying_refreshed or options_refreshed or dealer_refreshed),
            )
        except Exception as exc:
            post_ingestion_failed = True
            print(f"Market overview refresh failed: {type(exc).__name__}: {exc}")

    if not post_ingestion_failed:
        try:
            _run_market_intelligence(args)
        except Exception as exc:
            post_ingestion_failed = True
            print(f"Market intelligence refresh failed: {type(exc).__name__}: {exc}")

    publication = None
    if not post_ingestion_failed:
        try:
            publication = _publish_scanner_state(args)
        except Exception as exc:
            post_ingestion_failed = True
            print(f"Published market state failed: {type(exc).__name__}: {exc}")

    if publication is not None and not publication.scanner_ready:
        post_ingestion_failed = True
        failed_checks = [
            check.name for check in publication.checks
            if check.required and check.status not in {"READY", "DEGRADED"}
        ]
        print(
            "Published market state is not scanner-ready"
            + (f": {', '.join(failed_checks)}" if failed_checks else "")
        )

    # --continue-on-error permits symbol/batch-level provider failures, but it must never
    # mask a failed derived-state refresh or an unusable scanner publication.
    lifecycle_completed_at = datetime.now(timezone.utc)
    _write_lifecycle_report(
        args,
        started_at=lifecycle_started_at,
        completed_at=lifecycle_completed_at,
        failed=failed,
        post_ingestion_failed=post_ingestion_failed,
        underlying_refreshed=underlying_refreshed,
        options_refreshed=options_refreshed,
        dealer_refreshed=dealer_refreshed,
        trend_refreshed=trend_refreshed,
        publication=publication,
    )
    if post_ingestion_failed:
        return 1
    return 0 if failed == 0 or args.continue_on_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
