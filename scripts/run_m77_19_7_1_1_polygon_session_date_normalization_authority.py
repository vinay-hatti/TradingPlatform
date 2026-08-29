#!/usr/bin/env python3
"""
M77.19.7.1 — Lifecycle / Lineage Classification & Replay Window Authority

Purpose
-------
Convert the M77.19.7 direct-Polygon history discovery authority into a
fail-closed, symbol-specific replay-window authority.

Key governance:
- Source authority must be M77.19.7 and must declare POLYGON_DIRECT_REST_API.
- price_history is never read.
- For symbols whose current-ticker history predates their reported list date,
  or which have declared ticker-change lineage, the replay start is re-derived
  directly from Polygon from an identity anchor date.
- Predecessor/successor histories are never concatenated.
- No production tables, services, scoring, thresholds, weights, or authority
  are changed.
- This script produces research authority only.

The script uses only Python's standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "M77.19.7.1.1-POLYGON-SESSION-DATE-NORMALIZATION-AUTHORITY-1.0"
EXPECTED_UPSTREAM_VERSION = (
    "M77.19.7-SYMBOL-SPECIFIC-POLYGON-HISTORICAL-AVAILABILITY-LIFECYCLE-AUTHORITY-1.0"
)
EXPECTED_HISTORY_SOURCE = "POLYGON_DIRECT_REST_API"
DEFAULT_BASE_URL = "https://api.polygon.io"
DEFAULT_WARMUP_SESSIONS = 300
DEFAULT_LIMIT = 5000


class AuthorityError(RuntimeError):
    pass


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


def write_csv_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol",
        "asset_type",
        "classification",
        "replay_window_status",
        "current_ticker_first_observation",
        "reported_list_date",
        "ticker_change_count",
        "identity_anchor_date",
        "identity_anchor_reason",
        "direct_polygon_revalidation_required",
        "direct_polygon_revalidation_status",
        "post_anchor_first_observation",
        "post_anchor_bar_count",
        "certified_replay_start",
        "certified_replay_end",
        "predecessor_join_authorized",
        "production_authority_effect",
        "blockers",
    ]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k) for k in fields}
            if isinstance(out["blockers"], list):
                out["blockers"] = "|".join(out["blockers"])
            writer.writerow(out)
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def max_date_str(*values: str | None) -> str | None:
    parsed = [(parse_date(v), v) for v in values if v]
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed[-1][1]


def current_ticker_segment(symbol_record: dict[str, Any]) -> dict[str, Any] | None:
    segments = symbol_record.get("segments") or []
    current = [s for s in segments if s.get("relationship") == "CURRENT_TICKER"]
    if len(current) == 1:
        return current[0]
    if len(current) > 1:
        raise AuthorityError(
            f"{symbol_record.get('symbol')}: multiple CURRENT_TICKER segments"
        )
    return None


def has_prelisting_history(symbol_record: dict[str, Any]) -> bool:
    first = parse_date(symbol_record.get("current_ticker_first_observation"))
    listed = parse_date(symbol_record.get("list_date"))
    return bool(first and listed and first < listed)


def classify_symbol(symbol_record: dict[str, Any]) -> dict[str, Any]:
    symbol = symbol_record["symbol"]
    ticker_change_count = int(symbol_record.get("ticker_change_count") or 0)
    prelisting = has_prelisting_history(symbol_record)
    current_segment = current_ticker_segment(symbol_record)
    list_date = symbol_record.get("list_date")
    current_event_date = current_segment.get("event_date") if current_segment else None

    metadata_incomplete = (
        symbol_record.get("ticker_details_status") != "AVAILABLE"
        or symbol_record.get("ticker_events_status") != "AVAILABLE"
    )

    anchor = None
    anchor_reason = "UPSTREAM_CURRENT_TICKER_WARMUP_AUTHORITY"

    if ticker_change_count > 0:
        # A current-ticker event is the strongest identity boundary available in
        # the upstream lineage evidence. A later list date remains binding.
        anchor = max_date_str(current_event_date, list_date)
        anchor_reason = "DECLARED_TICKER_CHANGE_CURRENT_SEGMENT_IDENTITY_BOUNDARY"
    elif prelisting:
        anchor = list_date
        anchor_reason = "PRELISTING_TICKER_HISTORY_CONTAMINATION_BOUNDARY"

    if ticker_change_count > 0 and prelisting:
        classification = "LINEAGE_AND_PRELISTING_HISTORY_REQUIRE_CURRENT_TICKER_REANCHOR"
    elif ticker_change_count > 0:
        classification = "DECLARED_LINEAGE_REQUIRE_CURRENT_TICKER_REANCHOR"
    elif prelisting:
        classification = "PRELISTING_TICKER_HISTORY_REQUIRE_REANCHOR"
    elif metadata_incomplete:
        classification = "CURRENT_TICKER_WINDOW_WITH_INCOMPLETE_REFERENCE_METADATA"
    else:
        classification = "CURRENT_TICKER_WINDOW_NO_IDENTITY_ANOMALY_DETECTED"

    blockers: list[str] = []
    if ticker_change_count > 0:
        blockers.append("PREDECESSOR_LINEAGE_JOIN_NOT_AUTHORIZED")
    if prelisting:
        blockers.append("PRELISTING_TICKER_HISTORY_NOT_AUTHORIZED")
    if metadata_incomplete:
        blockers.append("REFERENCE_METADATA_INCOMPLETE")
    if (ticker_change_count > 0 or prelisting) and not anchor:
        blockers.append("IDENTITY_ANCHOR_UNRESOLVED")

    return {
        "symbol": symbol,
        "asset_type": symbol_record.get("asset_type"),
        "classification": classification,
        "current_ticker_first_observation": symbol_record.get("current_ticker_first_observation"),
        "reported_list_date": list_date,
        "ticker_change_count": ticker_change_count,
        "identity_anchor_date": anchor,
        "identity_anchor_reason": anchor_reason,
        "direct_polygon_revalidation_required": bool(anchor),
        "blockers": blockers,
        "upstream_replay_eligibility": symbol_record.get("replay_eligibility"),
        "upstream_replay_start": symbol_record.get("current_ticker_first_replay_eligible_date"),
        "upstream_replay_end": symbol_record.get("current_ticker_last_observation"),
        "predecessor_join_authorized": False,
        "production_authority_effect": False,
    }


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


def polygon_get_json(
    url: str,
    api_key: str,
    request_interval: float,
    retries: int = 4,
) -> dict[str, Any]:
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
            headers={"User-Agent": "TradingPlatform-M77.19.7.1/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(min(2 ** attempt, 8))
    raise AuthorityError(f"Polygon request failed: {url}: {last_error}")


def polygon_aggregate_session_date(epoch_ms: int | float) -> str:
    """
    Normalize Polygon aggregate epoch milliseconds in UTC.

    Never use host-local time here. Polygon daily aggregate timestamps are
    absolute instants; converting them through the host timezone can move a
    U.S. market session into the prior calendar date (for example Monday into
    Sunday on an America/Chicago host).
    """
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).date().isoformat()


def assert_weekday_session_dates(symbol: str, observations: list[str]) -> None:
    weekend = [v for v in observations if date.fromisoformat(v).weekday() >= 5]
    if weekend:
        raise AuthorityError(
            f"{symbol}: Polygon daily aggregate normalization produced weekend "
            f"session dates: {weekend[:5]}"
        )


def fetch_post_anchor_history(
    symbol: str,
    anchor_date: str,
    end_date: str,
    api_key: str,
    base_url: str,
    warmup_sessions: int,
    request_interval: float,
) -> dict[str, Any]:
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = (
        f"{base_url.rstrip('/')}/v2/aggs/ticker/{encoded_symbol}/range/1/day/"
        f"{anchor_date}/{end_date}"
        f"?adjusted=true&sort=asc&limit={DEFAULT_LIMIT}"
    )
    payload = polygon_get_json(url, api_key, request_interval)
    results = payload.get("results") or []

    # We only need enough bars to establish the warmup boundary. Polygon's
    # aggregate endpoint can return more than 300 within the 5000 result cap.
    observations: list[str] = []
    for bar in results:
        ts = bar.get("t")
        if ts is None:
            continue
        d = polygon_aggregate_session_date(ts)
        if d >= anchor_date:
            observations.append(d)
    observations = sorted(set(observations))
    assert_weekday_session_dates(symbol, observations)

    replay_start = (
        observations[warmup_sessions - 1]
        if len(observations) >= warmup_sessions
        else None
    )
    return {
        "status": "OK",
        "request_id": payload.get("request_id"),
        "endpoint": f"/v2/aggs/ticker/{symbol}/range/1/day/{anchor_date}/{end_date}",
        "post_anchor_first_observation": observations[0] if observations else None,
        "post_anchor_bar_count": len(observations),
        "certified_replay_start": replay_start,
    }


def validate_upstream(authority: dict[str, Any]) -> None:
    if authority.get("version") != EXPECTED_UPSTREAM_VERSION:
        raise AuthorityError(
            f"Unexpected upstream version: {authority.get('version')!r}"
        )
    governance = authority.get("governance") or {}
    if governance.get("history_authority_source") != EXPECTED_HISTORY_SOURCE:
        raise AuthorityError("Upstream history authority is not direct Polygon REST")
    if governance.get("polygon_direct_query") is not True:
        raise AuthorityError("Upstream polygon_direct_query must be true")
    if governance.get("price_history_table_used") is not False:
        raise AuthorityError("Upstream price_history_table_used must be false")
    if governance.get("predecessor_successor_series_automatically_concatenated") is not False:
        raise AuthorityError("Automatic lineage concatenation must remain false")
    if authority.get("history_failure_count") != 0:
        raise AuthorityError("Upstream authority contains history query failures")
    if authority.get("symbol_specific_history_authority_ready") is not True:
        raise AuthorityError("Upstream symbol history authority is not READY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--authority-json",
        default="reports/m77_19_7_symbol_specific_polygon_history_authority.json",
    )
    parser.add_argument(
        "--output-json",
        default="reports/m77_19_7_1_1_polygon_session_date_normalization_authority.json",
    )
    parser.add_argument(
        "--output-csv",
        default="reports/m77_19_7_1_1_polygon_session_date_normalization_authority.csv",
    )
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--request-interval", type=float, default=0.05)
    parser.add_argument("--warmup-sessions", type=int, default=DEFAULT_WARMUP_SESSIONS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--no-direct-revalidation",
        action="store_true",
        help="Diagnostic only. Leaves anchor-dependent symbols BLOCKED; never certifies them.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    authority_path = Path(args.authority_json)
    if not authority_path.is_absolute():
        authority_path = project_root / authority_path
    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = project_root / output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute():
        output_csv = project_root / output_csv

    authority = load_json(authority_path)
    validate_upstream(authority)

    upstream_sha = sha256_file(authority_path)
    symbols = authority.get("symbols") or []
    classified = [classify_symbol(s) for s in symbols]

    to_revalidate = [r for r in classified if r["direct_polygon_revalidation_required"]]
    api_key = None if args.no_direct_revalidation else discover_api_key(project_root)
    if to_revalidate and not args.no_direct_revalidation and not api_key:
        raise AuthorityError(
            "Direct Polygon revalidation is required for lifecycle/lineage symbols, "
            "but POLYGON_API_KEY/POLYGON_KEY was not found in the environment or project .env"
        )

    end_date = (authority.get("polygon_query_contract") or {}).get("to")
    if not end_date:
        raise AuthorityError("Upstream Polygon query end date is missing")

    revalidation_by_symbol: dict[str, dict[str, Any]] = {}
    if to_revalidate and not args.no_direct_revalidation:
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
            futures = {
                pool.submit(
                    fetch_post_anchor_history,
                    row["symbol"],
                    row["identity_anchor_date"],
                    end_date,
                    api_key,
                    args.base_url,
                    args.warmup_sessions,
                    args.request_interval,
                ): row["symbol"]
                for row in to_revalidate
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    revalidation_by_symbol[symbol] = future.result()
                except Exception as exc:
                    revalidation_by_symbol[symbol] = {
                        "status": "ERROR",
                        "error": str(exc),
                        "post_anchor_first_observation": None,
                        "post_anchor_bar_count": 0,
                        "certified_replay_start": None,
                    }

    for row in classified:
        symbol = row["symbol"]
        if row["direct_polygon_revalidation_required"]:
            if args.no_direct_revalidation:
                row["direct_polygon_revalidation_status"] = "BLOCKED_NOT_EXECUTED"
                row["post_anchor_first_observation"] = None
                row["post_anchor_bar_count"] = 0
                row["certified_replay_start"] = None
                row["certified_replay_end"] = None
                row["replay_window_status"] = "BLOCKED_DIRECT_POLYGON_REVALIDATION_REQUIRED"
                row["blockers"].append("DIRECT_POLYGON_REVALIDATION_REQUIRED")
            else:
                result = revalidation_by_symbol[symbol]
                row["direct_polygon_revalidation_status"] = result["status"]
                row["post_anchor_first_observation"] = result.get("post_anchor_first_observation")
                row["post_anchor_bar_count"] = result.get("post_anchor_bar_count", 0)
                row["certified_replay_start"] = result.get("certified_replay_start")
                row["certified_replay_end"] = row["upstream_replay_end"]
                row["polygon_revalidation_request_id"] = result.get("request_id")
                row["polygon_revalidation_endpoint"] = result.get("endpoint")
                if result["status"] != "OK":
                    row["replay_window_status"] = "BLOCKED_POLYGON_REVALIDATION_FAILED"
                    row["certified_replay_start"] = None
                    row["certified_replay_end"] = None
                    row["blockers"].append("POLYGON_REVALIDATION_FAILED")
                    row["polygon_revalidation_error"] = result.get("error")
                elif not result.get("certified_replay_start"):
                    row["replay_window_status"] = "BLOCKED_INSUFFICIENT_POST_ANCHOR_WARMUP"
                    row["certified_replay_end"] = None
                    row["blockers"].append("INSUFFICIENT_POST_ANCHOR_WARMUP")
                else:
                    row["replay_window_status"] = "CERTIFIED_CURRENT_TICKER_WINDOW"
                    # The reanchored current-ticker window is certified, but
                    # predecessor lineage remains independently blocked.
                    row["blockers"] = [
                        b for b in row["blockers"]
                        if b != "PRELISTING_TICKER_HISTORY_NOT_AUTHORIZED"
                    ]
        else:
            row["direct_polygon_revalidation_status"] = "NOT_REQUIRED"
            row["post_anchor_first_observation"] = None
            row["post_anchor_bar_count"] = None
            if row["upstream_replay_eligibility"] == "ELIGIBLE_CURRENT_TICKER_WINDOW":
                row["certified_replay_start"] = row["upstream_replay_start"]
                row["certified_replay_end"] = row["upstream_replay_end"]
                row["replay_window_status"] = "CERTIFIED_CURRENT_TICKER_WINDOW"
            else:
                row["certified_replay_start"] = None
                row["certified_replay_end"] = None
                row["replay_window_status"] = "BLOCKED_UPSTREAM_INSUFFICIENT_WARMUP"
                row["blockers"].append("UPSTREAM_INSUFFICIENT_WARMUP")

    counts: dict[str, dict[str, int]] = {}
    for field in ("classification", "replay_window_status"):
        c: dict[str, int] = {}
        for row in classified:
            key = str(row[field])
            c[key] = c.get(key, 0) + 1
        counts[field] = dict(sorted(c.items()))

    prelisting_symbols = [
        r["symbol"] for r in classified
        if "PRELISTING" in r["classification"]
    ]
    lineage_symbols = [
        r["symbol"] for r in classified
        if r["ticker_change_count"] > 0
    ]
    certified_count = sum(
        1 for r in classified
        if r["replay_window_status"] == "CERTIFIED_CURRENT_TICKER_WINDOW"
    )
    blocked_count = len(classified) - certified_count

    report = {
        "version": VERSION,
        "status": (
            "READY_FOR_SYMBOL_SPECIFIC_HISTORICAL_REPLAY"
            if blocked_count == 0
            else "READY_WITH_BLOCKED_SYMBOLS"
        ),
        "governance": {
            "upstream_authority": str(authority_path),
            "upstream_authority_sha256": upstream_sha,
            "history_authority_source": "POLYGON_DIRECT_REST_API",
            "direct_polygon_revalidation_performed": not args.no_direct_revalidation,
            "price_history_table_used": False,
            "database_access": "NONE",
            "predecessor_successor_series_automatically_concatenated": False,
            "ticker_lineage_join_authorized": False,
            "symbol_specific_reconstruction_authorized": True,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
            "warmup_sessions": args.warmup_sessions,
            "threshold_search_or_optimization": False,
        },
        "materialized_symbol_count": len(classified),
        "certified_current_ticker_window_count": certified_count,
        "blocked_symbol_count": blocked_count,
        "prelisting_history_anomaly_symbol_count": len(prelisting_symbols),
        "prelisting_history_anomaly_symbols": prelisting_symbols,
        "ticker_change_lineage_symbol_count": len(lineage_symbols),
        "ticker_change_lineage_symbols": lineage_symbols,
        "counts": counts,
        "symbols": classified,
        "next_step": (
            "BUILD_M77_19_7_2_SYMBOL_SPECIFIC_HISTORICAL_REPLAY_MATERIALIZATION"
            if certified_count > 0
            else "RESOLVE_M77_19_7_1_BLOCKED_REPLAY_WINDOWS"
        ),
    }

    write_json_atomic(output_json, report)
    write_csv_atomic(output_csv, classified)

    print("=== M77.19.7.1.1 POLYGON SESSION-DATE NORMALIZATION AUTHORITY ===")
    print(f"upstream_authority_sha256: {upstream_sha}")
    print(f"materialized_symbol_count: {len(classified)}")
    print(f"prelisting_history_anomaly_symbol_count: {len(prelisting_symbols)}")
    print(f"ticker_change_lineage_symbol_count: {len(lineage_symbols)}")
    print(f"direct_polygon_revalidation_required_count: {len(to_revalidate)}")
    print(f"certified_current_ticker_window_count: {certified_count}")
    print(f"blocked_symbol_count: {blocked_count}")
    print(f"full_23_year_reconstruction_authorized: False")
    print(f"ticker_lineage_join_authorized: False")
    print(f"production_authority_effect: False")
    print(f"report: {output_json}")
    print(f"csv: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
