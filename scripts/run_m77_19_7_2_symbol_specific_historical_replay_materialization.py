#!/usr/bin/env python3
"""
M77.19.7.2 — Symbol-Specific Historical Replay Materialization

Materialize immutable, symbol-specific daily OHLCV replay input directly from
Polygon for the exact current-ticker windows certified by M77.19.7.1.1.

This stage intentionally does NOT execute Stock Intelligence and does NOT
resample daily bars into weekly/monthly state. It freezes the authorized daily
source bars, including the pre-replay warmup segment, so downstream point-in-
time replay can be performed without consulting production price_history.

Governance:
- upstream M77.19.7.1.1 authority is SHA-pinned;
- only CERTIFIED_CURRENT_TICKER_WINDOW symbols are queried;
- blocked symbols are carried forward and never queried/materialized;
- Polygon Direct REST is the only market-history source;
- price_history and all database access are prohibited;
- predecessor/successor histories are never concatenated;
- materialization begins at the authorized current-ticker observation boundary,
  before replay_start, so the 300-session warmup remains available;
- replay scoring remains prohibited before certified_replay_start;
- no production services/tables/authority are modified.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "M77.19.7.2-SYMBOL-SPECIFIC-HISTORICAL-REPLAY-MATERIALIZATION-1.0"
EXPECTED_UPSTREAM_VERSION = "M77.19.7.1.1-POLYGON-SESSION-DATE-NORMALIZATION-AUTHORITY-1.0"
EXPECTED_UPSTREAM_SHA256 = "c1e657077ad0de4495cfa93c1ebecb864e6243ae105c7c562c55bb33f462b04a"
EXPECTED_MATERIALIZED_SYMBOL_COUNT = 611
EXPECTED_CERTIFIED_COUNT = 602
EXPECTED_BLOCKED_COUNT = 9
EXPECTED_WARMUP_SESSIONS = 300
EXPECTED_HISTORY_SOURCE = "POLYGON_DIRECT_REST_API"
DEFAULT_BASE_URL = "https://api.polygon.io"
DEFAULT_LIMIT = 50000
BAR_FIELDS = ["session_date", "open", "high", "low", "close", "volume", "vwap", "transactions"]


class MaterializationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def write_csv_atomic(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k) for k in fields}
            if isinstance(out.get("blockers"), list):
                out["blockers"] = "|".join(out["blockers"])
            writer.writerow(out)
    os.replace(tmp, path)


def write_bars_gzip_atomic(path: Path, bars: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="", compresslevel=6) as fh:
        writer = csv.DictWriter(fh, fieldnames=BAR_FIELDS)
        writer.writeheader()
        for row in bars:
            writer.writerow({k: row.get(k) for k in BAR_FIELDS})
    os.replace(tmp, path)


def polygon_aggregate_session_date(epoch_ms: int | float) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).date().isoformat()


def assert_weekday_session_dates(symbol: str, observations: list[str]) -> None:
    weekends = [d for d in observations if date.fromisoformat(d).weekday() >= 5]
    if weekends:
        raise MaterializationError(
            f"{symbol}: weekend daily sessions after UTC normalization: {weekends[:5]}"
        )


def discover_api_key(project_root: Path) -> str | None:
    for name in ("POLYGON_API_KEY", "POLYGON_KEY"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    env_path = project_root / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"POLYGON_API_KEY", "POLYGON_KEY"}:
                return value.strip().strip('"').strip("'")
    return None


def polygon_get_json(url: str, api_key: str, request_interval: float, retries: int = 5) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(k == "apiKey" for k, _ in query):
        query.append(("apiKey", api_key))
    final_url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        if request_interval > 0:
            time.sleep(request_interval)
        req = urllib.request.Request(
            final_url,
            headers={"User-Agent": "TradingPlatform-M77.19.7.2/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            status = payload.get("status")
            if status not in (None, "OK", "DELAYED"):
                raise MaterializationError(f"Polygon status={status!r} for {url}")
            return payload
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, MaterializationError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(min(2 ** attempt, 10))
    raise MaterializationError(f"Polygon request failed: {url}: {last_error}")


def validate_upstream(authority: dict[str, Any], authority_path: Path) -> None:
    actual_sha = sha256_file(authority_path)
    if actual_sha != EXPECTED_UPSTREAM_SHA256:
        raise MaterializationError(
            "M77.19.7.1.1 authority SHA mismatch; fail closed. "
            f"expected={EXPECTED_UPSTREAM_SHA256} actual={actual_sha}"
        )
    if authority.get("version") != EXPECTED_UPSTREAM_VERSION:
        raise MaterializationError(f"Unexpected upstream version: {authority.get('version')!r}")
    governance = authority.get("governance") or {}
    required = {
        "history_authority_source": EXPECTED_HISTORY_SOURCE,
        "price_history_table_used": False,
        "database_access": "NONE",
        "predecessor_successor_series_automatically_concatenated": False,
        "ticker_lineage_join_authorized": False,
        "symbol_specific_reconstruction_authorized": True,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "warmup_sessions": EXPECTED_WARMUP_SESSIONS,
        "threshold_search_or_optimization": False,
    }
    for key, expected in required.items():
        if governance.get(key) != expected:
            raise MaterializationError(
                f"Upstream governance {key} mismatch: expected={expected!r} actual={governance.get(key)!r}"
            )
    if authority.get("materialized_symbol_count") != EXPECTED_MATERIALIZED_SYMBOL_COUNT:
        raise MaterializationError("Unexpected upstream materialized_symbol_count")
    if authority.get("certified_current_ticker_window_count") != EXPECTED_CERTIFIED_COUNT:
        raise MaterializationError("Unexpected upstream certified count")
    if authority.get("blocked_symbol_count") != EXPECTED_BLOCKED_COUNT:
        raise MaterializationError("Unexpected upstream blocked count")
    if len(authority.get("symbols") or []) != EXPECTED_MATERIALIZED_SYMBOL_COUNT:
        raise MaterializationError("Upstream symbol array count mismatch")

    certified = 0
    blocked = 0
    seen: set[str] = set()
    for row in authority.get("symbols") or []:
        symbol = row.get("symbol")
        if not symbol or symbol in seen:
            raise MaterializationError(f"Duplicate or empty symbol in upstream authority: {symbol!r}")
        seen.add(symbol)
        status = row.get("replay_window_status")
        start = row.get("certified_replay_start")
        end = row.get("certified_replay_end")
        if status == "CERTIFIED_CURRENT_TICKER_WINDOW":
            certified += 1
            if not start or not end:
                raise MaterializationError(f"{symbol}: certified window missing boundary")
            if date.fromisoformat(start).weekday() >= 5 or date.fromisoformat(end).weekday() >= 5:
                raise MaterializationError(f"{symbol}: certified replay boundary falls on weekend")
        else:
            blocked += 1
            if start is not None or end is not None:
                raise MaterializationError(f"{symbol}: blocked symbol unexpectedly has certified replay boundaries")
    if certified != EXPECTED_CERTIFIED_COUNT or blocked != EXPECTED_BLOCKED_COUNT:
        raise MaterializationError("Upstream certified/blocked row counts do not reconcile")


def materialization_start_for(row: dict[str, Any]) -> str:
    if row.get("replay_window_status") != "CERTIFIED_CURRENT_TICKER_WINDOW":
        raise MaterializationError(f"{row.get('symbol')}: materialization requested for non-certified symbol")
    if row.get("direct_polygon_revalidation_required"):
        start = row.get("post_anchor_first_observation")
        source = "POST_ANCHOR_FIRST_OBSERVATION"
    else:
        start = row.get("current_ticker_first_observation")
        source = "CURRENT_TICKER_FIRST_OBSERVATION"
    if not start:
        raise MaterializationError(
            f"{row.get('symbol')}: authorized warmup materialization boundary missing ({source})"
        )
    replay_start = row.get("certified_replay_start")
    if date.fromisoformat(start) > date.fromisoformat(replay_start):
        raise MaterializationError(
            f"{row.get('symbol')}: materialization_start {start} is after replay_start {replay_start}"
        )
    return start


def bar_from_polygon(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("t") is None:
        raise MaterializationError("Polygon aggregate missing timestamp")
    return {
        "session_date": polygon_aggregate_session_date(raw["t"]),
        "open": raw.get("o"),
        "high": raw.get("h"),
        "low": raw.get("l"),
        "close": raw.get("c"),
        "volume": raw.get("v"),
        "vwap": raw.get("vw"),
        "transactions": raw.get("n"),
    }


def validate_bars(
    symbol: str,
    bars: list[dict[str, Any]],
    materialization_start: str,
    replay_start: str,
    replay_end: str,
    warmup_sessions: int,
) -> dict[str, Any]:
    if not bars:
        raise MaterializationError(f"{symbol}: Polygon returned no daily bars")
    dates = [str(b["session_date"]) for b in bars]
    if dates != sorted(dates):
        raise MaterializationError(f"{symbol}: daily bars are not ascending")
    if len(dates) != len(set(dates)):
        raise MaterializationError(f"{symbol}: duplicate daily session dates")
    assert_weekday_session_dates(symbol, dates)
    if dates[0] != materialization_start:
        raise MaterializationError(
            f"{symbol}: first materialized session mismatch expected={materialization_start} actual={dates[0]}"
        )
    if dates[-1] != replay_end:
        raise MaterializationError(
            f"{symbol}: last materialized session mismatch expected={replay_end} actual={dates[-1]}"
        )
    try:
        replay_idx = dates.index(replay_start)
    except ValueError as exc:
        raise MaterializationError(f"{symbol}: certified replay_start {replay_start} absent from Polygon bars") from exc
    available_warmup_sessions = replay_idx + 1
    if available_warmup_sessions < warmup_sessions:
        raise MaterializationError(
            f"{symbol}: only {available_warmup_sessions} sessions through replay_start; "
            f"requires >= {warmup_sessions}"
        )
    required_ohlc = ("open", "high", "low", "close")
    for i, bar in enumerate(bars):
        if any(bar.get(k) is None for k in required_ohlc):
            raise MaterializationError(f"{symbol}: null OHLC at {bar.get('session_date')} index={i}")
    return {
        "bar_count": len(bars),
        "warmup_session_count_through_replay_start": available_warmup_sessions,
        "replay_scored_session_count": len(bars) - replay_idx,
        "first_session": dates[0],
        "last_session": dates[-1],
    }


def fetch_symbol_bars(
    row: dict[str, Any],
    api_key: str,
    base_url: str,
    request_interval: float,
    warmup_sessions: int,
) -> dict[str, Any]:
    symbol = row["symbol"]
    start = materialization_start_for(row)
    replay_start = row["certified_replay_start"]
    end = row["certified_replay_end"]
    encoded = urllib.parse.quote(symbol, safe="")
    url = (
        f"{base_url.rstrip('/')}/v2/aggs/ticker/{encoded}/range/1/day/{start}/{end}"
        f"?adjusted=true&sort=asc&limit={DEFAULT_LIMIT}"
    )
    payload = polygon_get_json(url, api_key, request_interval)
    results = payload.get("results") or []
    bars = [bar_from_polygon(raw) for raw in results]
    metrics = validate_bars(symbol, bars, start, replay_start, end, warmup_sessions)
    return {
        "symbol": symbol,
        "bars": bars,
        "request_id": payload.get("request_id"),
        "endpoint": f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
        "query_url_without_key": url,
        "materialization_start": start,
        "replay_start": replay_start,
        "replay_end": end,
        **metrics,
    }


def safe_symbol_filename(symbol: str) -> str:
    return urllib.parse.quote(symbol, safe="").replace("%", "_")


def expected_symbol_signature(upstream_sha: str, row: dict[str, Any], start: str) -> str:
    payload = {
        "upstream_sha256": upstream_sha,
        "symbol": row["symbol"],
        "materialization_start": start,
        "replay_start": row["certified_replay_start"],
        "replay_end": row["certified_replay_end"],
        "adjusted": True,
        "timespan": "day",
        "multiplier": 1,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def maybe_resume_symbol(
    row: dict[str, Any], upstream_sha: str, data_dir: Path, meta_dir: Path
) -> dict[str, Any] | None:
    symbol = row["symbol"]
    start = materialization_start_for(row)
    stem = safe_symbol_filename(symbol)
    data_path = data_dir / f"{stem}.daily.csv.gz"
    meta_path = meta_dir / f"{stem}.json"
    if not data_path.exists() or not meta_path.exists():
        return None
    try:
        meta = load_json(meta_path)
    except Exception:
        return None
    signature = expected_symbol_signature(upstream_sha, row, start)
    if meta.get("materialization_signature") != signature:
        return None
    if meta.get("data_sha256") != sha256_file(data_path):
        return None
    if meta.get("status") != "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW":
        return None
    return dict(meta, resumed=True, data_file=str(data_path), metadata_file=str(meta_path))


def persist_symbol_result(
    result: dict[str, Any], row: dict[str, Any], upstream_sha: str, data_dir: Path, meta_dir: Path
) -> dict[str, Any]:
    symbol = result["symbol"]
    stem = safe_symbol_filename(symbol)
    data_path = data_dir / f"{stem}.daily.csv.gz"
    meta_path = meta_dir / f"{stem}.json"
    bars = result.pop("bars")
    write_bars_gzip_atomic(data_path, bars)
    data_sha = sha256_file(data_path)
    signature = expected_symbol_signature(upstream_sha, row, result["materialization_start"])
    meta = {
        "version": VERSION,
        "status": "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW",
        "symbol": symbol,
        "asset_type": row.get("asset_type"),
        "classification": row.get("classification"),
        "materialization_signature": signature,
        "upstream_authority_sha256": upstream_sha,
        "history_source": "POLYGON_DIRECT_REST_API",
        "adjusted": True,
        "timespan": "day",
        "multiplier": 1,
        "materialization_start": result["materialization_start"],
        "replay_start": result["replay_start"],
        "replay_end": result["replay_end"],
        "warmup_sessions_required": EXPECTED_WARMUP_SESSIONS,
        "warmup_session_count_through_replay_start": result["warmup_session_count_through_replay_start"],
        "bar_count": result["bar_count"],
        "replay_scored_session_count": result["replay_scored_session_count"],
        "first_session": result["first_session"],
        "last_session": result["last_session"],
        "polygon_request_id": result.get("request_id"),
        "polygon_endpoint": result.get("endpoint"),
        "data_file": str(data_path),
        "data_sha256": data_sha,
        "price_history_table_used": False,
        "database_access": "NONE",
        "predecessor_join_authorized": False,
        "weekly_monthly_resampling_performed": False,
        "stock_intelligence_replay_executed": False,
        "production_authority_effect": False,
        "resumed": False,
    }
    write_json_atomic(meta_path, meta)
    return dict(meta, metadata_file=str(meta_path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--authority-json",
        default="reports/m77_19_7_1_1_polygon_session_date_normalization_authority.json",
    )
    parser.add_argument(
        "--output-root",
        default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization",
    )
    parser.add_argument(
        "--output-json",
        default="reports/m77_19_7_2_symbol_specific_historical_replay_materialization.json",
    )
    parser.add_argument(
        "--output-csv",
        default="reports/m77_19_7_2_symbol_specific_historical_replay_materialization.csv",
    )
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--request-interval", type=float, default=0.05)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--symbols",
        default=None,
        help="Diagnostic subset only, comma-separated. Full authority status remains INCOMPLETE until all 602 are materialized.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    authority_path = Path(args.authority_json)
    if not authority_path.is_absolute():
        authority_path = project_root / authority_path
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = project_root / output_root
    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = project_root / output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute():
        output_csv = project_root / output_csv

    authority = load_json(authority_path)
    validate_upstream(authority, authority_path)
    upstream_sha = sha256_file(authority_path)
    api_key = discover_api_key(project_root)
    if not api_key:
        raise MaterializationError(
            "POLYGON_API_KEY/POLYGON_KEY not found in environment or project .env"
        )

    certified_rows = [
        r for r in authority["symbols"]
        if r.get("replay_window_status") == "CERTIFIED_CURRENT_TICKER_WINDOW"
    ]
    blocked_rows = [
        r for r in authority["symbols"]
        if r.get("replay_window_status") != "CERTIFIED_CURRENT_TICKER_WINDOW"
    ]
    selected_symbols: set[str] | None = None
    if args.symbols:
        selected_symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
        unknown = selected_symbols - {r["symbol"] for r in certified_rows}
        if unknown:
            raise MaterializationError(f"Requested symbols are not certified: {sorted(unknown)}")

    data_dir = output_root / "daily_bars"
    meta_dir = output_root / "symbol_metadata"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    records_by_symbol: dict[str, dict[str, Any]] = {}
    rows_to_fetch: list[dict[str, Any]] = []
    for row in certified_rows:
        symbol = row["symbol"]
        if selected_symbols is not None and symbol not in selected_symbols:
            continue
        if args.resume:
            resumed = maybe_resume_symbol(row, upstream_sha, data_dir, meta_dir)
            if resumed:
                records_by_symbol[symbol] = resumed
                continue
        rows_to_fetch.append(row)

    failures: list[dict[str, Any]] = []
    if rows_to_fetch:
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
            futures = {
                pool.submit(
                    fetch_symbol_bars,
                    row,
                    api_key,
                    args.base_url,
                    args.request_interval,
                    EXPECTED_WARMUP_SESSIONS,
                ): row
                for row in rows_to_fetch
            }
            completed = 0
            total = len(rows_to_fetch)
            for future in as_completed(futures):
                row = futures[future]
                symbol = row["symbol"]
                completed += 1
                try:
                    result = future.result()
                    meta = persist_symbol_result(result, row, upstream_sha, data_dir, meta_dir)
                    records_by_symbol[symbol] = meta
                    print(
                        f"[{completed}/{total}] {symbol}: MATERIALIZED bars={meta['bar_count']} "
                        f"warmup_through_replay_start={meta['warmup_session_count_through_replay_start']}"
                    )
                except Exception as exc:
                    failure = {
                        "symbol": symbol,
                        "status": "MATERIALIZATION_FAILED",
                        "error": str(exc),
                    }
                    failures.append(failure)
                    records_by_symbol[symbol] = failure
                    print(f"[{completed}/{total}] {symbol}: FAILED {exc}", file=sys.stderr)

    report_rows: list[dict[str, Any]] = []
    successful_all = 0
    for row in certified_rows:
        symbol = row["symbol"]
        record = records_by_symbol.get(symbol)
        if record is None and args.resume:
            record = maybe_resume_symbol(row, upstream_sha, data_dir, meta_dir)
        if record and record.get("status") == "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW":
            successful_all += 1
            report_rows.append({
                "symbol": symbol,
                "asset_type": row.get("asset_type"),
                "upstream_replay_window_status": row.get("replay_window_status"),
                "materialization_status": record.get("status"),
                "materialization_start": record.get("materialization_start"),
                "replay_start": record.get("replay_start"),
                "replay_end": record.get("replay_end"),
                "bar_count": record.get("bar_count"),
                "warmup_session_count_through_replay_start": record.get("warmup_session_count_through_replay_start"),
                "replay_scored_session_count": record.get("replay_scored_session_count"),
                "data_sha256": record.get("data_sha256"),
                "resumed": record.get("resumed", False),
                "blockers": [],
            })
        else:
            report_rows.append({
                "symbol": symbol,
                "asset_type": row.get("asset_type"),
                "upstream_replay_window_status": row.get("replay_window_status"),
                "materialization_status": (record or {}).get("status", "NOT_MATERIALIZED"),
                "materialization_start": materialization_start_for(row),
                "replay_start": row.get("certified_replay_start"),
                "replay_end": row.get("certified_replay_end"),
                "bar_count": None,
                "warmup_session_count_through_replay_start": None,
                "replay_scored_session_count": None,
                "data_sha256": None,
                "resumed": False,
                "blockers": [(record or {}).get("error", "NOT_MATERIALIZED")],
            })

    for row in blocked_rows:
        report_rows.append({
            "symbol": row["symbol"],
            "asset_type": row.get("asset_type"),
            "upstream_replay_window_status": row.get("replay_window_status"),
            "materialization_status": "CARRIED_FORWARD_BLOCKED_NO_POLYGON_MATERIALIZATION",
            "materialization_start": None,
            "replay_start": None,
            "replay_end": None,
            "bar_count": None,
            "warmup_session_count_through_replay_start": None,
            "replay_scored_session_count": None,
            "data_sha256": None,
            "resumed": False,
            "blockers": row.get("blockers") or [],
        })

    report_rows.sort(key=lambda r: r["symbol"])
    fully_materialized = successful_all == EXPECTED_CERTIFIED_COUNT
    report = {
        "version": VERSION,
        "status": "READY" if fully_materialized else "INCOMPLETE_RETRY_REQUIRED",
        "governance": {
            "upstream_authority": str(authority_path),
            "upstream_authority_sha256": upstream_sha,
            "upstream_authority_sha_pinned": True,
            "history_source": "POLYGON_DIRECT_REST_API",
            "polygon_direct_query": True,
            "adjusted_daily_bars": True,
            "price_history_table_used": False,
            "database_access": "NONE",
            "predecessor_successor_series_automatically_concatenated": False,
            "ticker_lineage_join_authorized": False,
            "blocked_symbols_queried": False,
            "warmup_sessions_required": EXPECTED_WARMUP_SESSIONS,
            "replay_before_certified_start_authorized": False,
            "weekly_monthly_resampling_performed": False,
            "stock_intelligence_replay_executed": False,
            "full_23_year_reconstruction_authorized": False,
            "threshold_search_or_optimization": False,
            "production_authority_effect": False,
        },
        "upstream_materialized_symbol_count": EXPECTED_MATERIALIZED_SYMBOL_COUNT,
        "upstream_certified_symbol_count": EXPECTED_CERTIFIED_COUNT,
        "upstream_blocked_symbol_count": EXPECTED_BLOCKED_COUNT,
        "certified_symbol_materialized_count": successful_all,
        "certified_symbol_materialization_failure_count": EXPECTED_CERTIFIED_COUNT - successful_all,
        "blocked_symbol_carried_forward_count": len(blocked_rows),
        "output_root": str(output_root),
        "symbols": report_rows,
        "next_step": (
            "BUILD_M77_19_7_3_POINT_IN_TIME_SYMBOL_SPECIFIC_STOCK_INTELLIGENCE_REPLAY"
            if fully_materialized
            else "RESUME_M77_19_7_2_SYMBOL_SPECIFIC_HISTORICAL_REPLAY_MATERIALIZATION"
        ),
    }
    write_json_atomic(output_json, report)
    write_csv_atomic(
        output_csv,
        report_rows,
        [
            "symbol", "asset_type", "upstream_replay_window_status", "materialization_status",
            "materialization_start", "replay_start", "replay_end", "bar_count",
            "warmup_session_count_through_replay_start", "replay_scored_session_count",
            "data_sha256", "resumed", "blockers",
        ],
    )

    print("=== M77.19.7.2 SYMBOL-SPECIFIC HISTORICAL REPLAY MATERIALIZATION ===")
    print(f"upstream_authority_sha256: {upstream_sha}")
    print(f"upstream_certified_symbol_count: {EXPECTED_CERTIFIED_COUNT}")
    print(f"certified_symbol_materialized_count: {successful_all}")
    print(f"certified_symbol_materialization_failure_count: {EXPECTED_CERTIFIED_COUNT - successful_all}")
    print(f"blocked_symbol_carried_forward_count: {len(blocked_rows)}")
    print("history_source: POLYGON_DIRECT_REST_API")
    print("price_history_table_used: False")
    print("database_access: NONE")
    print("weekly_monthly_resampling_performed: False")
    print("stock_intelligence_replay_executed: False")
    print("production_authority_effect: False")
    print(f"report: {output_json}")
    print(f"csv: {output_csv}")
    print(f"output_root: {output_root}")
    return 0 if fully_materialized else 2


if __name__ == "__main__":
    raise SystemExit(main())
