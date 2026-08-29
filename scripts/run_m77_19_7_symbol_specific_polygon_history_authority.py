#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

VERSION = "M77.19.7-SYMBOL-SPECIFIC-POLYGON-HISTORICAL-AVAILABILITY-LIFECYCLE-AUTHORITY-1.0"

POLYGON_PROVIDER_HISTORY_FLOOR = dt.date(2003, 9, 10)
DEFAULT_POLYGON_BASE_URL = "https://api.polygon.io"
DEFAULT_WARMUP_SESSIONS = 300
EARLIEST_BAR_QUERY_LIMIT = 400

# Governance: direct provider authority only. This runner must not import or query the platform DB.
DATABASE_ACCESS = "NONE"
HISTORY_AUTHORITY_SOURCE = "POLYGON_DIRECT_REST_API"
PRICE_HISTORY_AUTHORITY_ALLOWED = False
PRODUCTION_AUTHORITY_EFFECT = False
FULL_23_YEAR_RECONSTRUCTION_AUTHORIZED = False


class PolygonError(RuntimeError):
    pass


@dataclass
class ApiEvidence:
    endpoint: str
    status: str
    request_id: str | None = None
    error: str | None = None


@dataclass
class TickerSegment:
    ticker: str
    relationship: str
    event_date: str | None = None
    first_observation: str | None = None
    warmup_eligible_date: str | None = None
    last_observation: str | None = None
    first_bar_count_returned: int = 0
    history_status: str = "UNQUERIED"
    adjusted: bool = True
    request_id_first: str | None = None
    request_id_last: str | None = None


@dataclass
class SymbolAuthority:
    symbol: str
    asset_type: str | None = None
    name: str | None = None
    current_ticker_first_observation: str | None = None
    current_ticker_last_observation: str | None = None
    current_ticker_first_replay_eligible_date: str | None = None
    lineage_earliest_polygon_observation: str | None = None
    lineage_earliest_replay_eligible_date: str | None = None
    history_years_current_ticker: float | None = None
    history_years_lineage_envelope: float | None = None
    current_ticker_history_status: str = "UNQUERIED"
    replay_eligibility: str = "UNRESOLVED"
    ticker_details_status: str = "UNQUERIED"
    ticker_events_status: str = "UNQUERIED"
    split_history_status: str = "UNQUERIED"
    active: bool | None = None
    list_date: str | None = None
    delisted_utc: str | None = None
    primary_exchange: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    ticker_change_count: int = 0
    split_count: int = 0
    lifecycle_flags: list[str] = field(default_factory=list)
    lineage_join_authorized: bool = False
    segments: list[TickerSegment] = field(default_factory=list)
    evidence: list[ApiEvidence] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class RateGate:
    def __init__(self, min_interval_seconds: float):
        self.min_interval = max(0.0, float(min_interval_seconds))
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self.min_interval


class PolygonDirectClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        retries: int,
        min_interval_seconds: float,
    ):
        if not api_key:
            raise PolygonError(
                "Polygon API key missing. Set POLYGON_API_KEY or pass --polygon-api-key-env."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.retries = int(retries)
        self.gate = RateGate(min_interval_seconds)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        q = dict(params or {})
        q["apiKey"] = self.api_key
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(q)}"
        safe_url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            self.gate.wait()
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "TradingPlatform-M77.19.7/1.0",
                        "Accept": "application/json",
                    },
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                if isinstance(payload, dict) and payload.get("status") in ("ERROR", "NOT_AUTHORIZED"):
                    raise PolygonError(
                        f"{safe_url} status={payload.get('status')} "
                        f"error={payload.get('error') or payload.get('message')}"
                    )
                return payload
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:1000]
                except Exception:
                    pass
                last_error = PolygonError(
                    f"{safe_url} HTTP {exc.code}: {body or exc.reason}"
                )
                if exc.code == 429 or 500 <= exc.code < 600:
                    time.sleep(min(30.0, (2 ** attempt) + random.random()))
                    continue
                raise last_error
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, PolygonError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(30.0, (2 ** attempt) + random.random()))
                    continue
                raise PolygonError(f"{safe_url}: {exc}") from exc

        raise PolygonError(str(last_error or "unknown Polygon API error"))

    def aggs_first(self, ticker: str, end_date: dt.date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        path = (
            f"/v2/aggs/ticker/{urllib.parse.quote(ticker, safe=':.-')}"
            f"/range/1/day/{POLYGON_PROVIDER_HISTORY_FLOOR.isoformat()}/{end_date.isoformat()}"
        )
        payload = self.get(
            path,
            {
                "adjusted": "true",
                "sort": "asc",
                "limit": EARLIEST_BAR_QUERY_LIMIT,
            },
        )
        return list(payload.get("results") or []), payload

    def aggs_last(self, ticker: str, end_date: dt.date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        path = (
            f"/v2/aggs/ticker/{urllib.parse.quote(ticker, safe=':.-')}"
            f"/range/1/day/{POLYGON_PROVIDER_HISTORY_FLOOR.isoformat()}/{end_date.isoformat()}"
        )
        payload = self.get(
            path,
            {
                "adjusted": "true",
                "sort": "desc",
                "limit": 1,
            },
        )
        return list(payload.get("results") or []), payload

    def ticker_details(self, ticker: str) -> dict[str, Any]:
        return self.get(f"/v3/reference/tickers/{urllib.parse.quote(ticker, safe=':.-')}")

    def ticker_events(self, ticker: str) -> dict[str, Any]:
        return self.get(
            f"/vX/reference/tickers/{urllib.parse.quote(ticker, safe=':.-')}/events"
        )

    def splits(self, ticker: str) -> dict[str, Any]:
        return self.get(
            "/stocks/v1/splits",
            {
                "ticker": ticker,
                "limit": 1000,
                "sort": "execution_date.asc",
            },
        )


def millis_to_date(value: Any) -> str | None:
    if value is None:
        return None
    return dt.datetime.fromtimestamp(float(value) / 1000.0, tz=dt.timezone.utc).date().isoformat()


def years_between(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    da = dt.date.fromisoformat(a)
    db = dt.date.fromisoformat(b)
    return round((db - da).days / 365.2425, 4)


def detect_symbol_column(fieldnames: list[str]) -> str:
    lowered = {x.strip().lower(): x for x in fieldnames}
    for candidate in ("symbol", "ticker", "ticker_symbol"):
        if candidate in lowered:
            return lowered[candidate]
    raise SystemExit(
        f"FAIL CLOSED: universe CSV has no recognized symbol column; columns={fieldnames}"
    )


def load_universe(path: Path) -> list[tuple[str, str | None]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise SystemExit("FAIL CLOSED: universe CSV has no header")
        symbol_col = detect_symbol_column(reader.fieldnames)
        lowered = {x.strip().lower(): x for x in reader.fieldnames}
        asset_col = None
        for c in ("asset_type", "type", "security_type"):
            if c in lowered:
                asset_col = lowered[c]
                break
        out: list[tuple[str, str | None]] = []
        seen = set()
        for row in reader:
            symbol = str(row.get(symbol_col) or "").strip().upper()
            if not symbol or symbol.startswith("#") or symbol in seen:
                continue
            seen.add(symbol)
            asset = str(row.get(asset_col) or "").strip().upper() if asset_col else None
            out.append((symbol, asset or None))
    if not out:
        raise SystemExit("FAIL CLOSED: canonical universe is empty")
    return out


def parse_ticker_lineage(current_symbol: str, payload: dict[str, Any]) -> list[tuple[str, str | None]]:
    result = payload.get("results") or {}
    events = list(result.get("events") or [])
    found: list[tuple[str, str | None]] = []
    seen = set()
    for event in events:
        if event.get("type") != "ticker_change":
            continue
        ticker = str((event.get("ticker_change") or {}).get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        found.append((ticker, str(event.get("date") or "") or None))
    if current_symbol not in seen:
        found.append((current_symbol, None))
    found.sort(key=lambda x: (x[1] is None, x[1] or "9999-12-31", x[0]))
    return found


def query_segment(
    client: PolygonDirectClient,
    ticker: str,
    relationship: str,
    event_date: str | None,
    end_date: dt.date,
    warmup_sessions: int,
) -> TickerSegment:
    seg = TickerSegment(ticker=ticker, relationship=relationship, event_date=event_date)
    try:
        first_rows, first_payload = client.aggs_first(ticker, end_date)
        seg.request_id_first = first_payload.get("request_id")
        seg.first_bar_count_returned = len(first_rows)
        if first_rows:
            seg.first_observation = millis_to_date(first_rows[0].get("t"))
            if len(first_rows) >= warmup_sessions:
                seg.warmup_eligible_date = millis_to_date(first_rows[warmup_sessions - 1].get("t"))
            seg.history_status = "AVAILABLE"
        else:
            seg.history_status = "NO_AGGREGATE_HISTORY_RETURNED"
    except Exception as exc:
        seg.history_status = "AGGREGATE_QUERY_FAILED"
        return seg

    try:
        last_rows, last_payload = client.aggs_last(ticker, end_date)
        seg.request_id_last = last_payload.get("request_id")
        if last_rows:
            seg.last_observation = millis_to_date(last_rows[0].get("t"))
    except Exception:
        if seg.history_status == "AVAILABLE":
            seg.history_status = "AVAILABLE_LAST_DATE_QUERY_FAILED"
    return seg


def analyze_symbol(
    symbol: str,
    asset_type: str | None,
    client: PolygonDirectClient,
    end_date: dt.date,
    warmup_sessions: int,
) -> SymbolAuthority:
    out = SymbolAuthority(symbol=symbol, asset_type=asset_type)

    details_payload = None
    try:
        details_payload = client.ticker_details(symbol)
        result = details_payload.get("results") or {}
        out.name = result.get("name")
        out.active = result.get("active")
        out.list_date = result.get("list_date")
        out.delisted_utc = result.get("delisted_utc")
        out.primary_exchange = result.get("primary_exchange")
        out.composite_figi = result.get("composite_figi")
        out.share_class_figi = result.get("share_class_figi")
        out.ticker_details_status = "AVAILABLE"
        out.evidence.append(
            ApiEvidence(
                endpoint=f"/v3/reference/tickers/{symbol}",
                status="OK",
                request_id=details_payload.get("request_id"),
            )
        )
    except Exception as exc:
        out.ticker_details_status = "UNAVAILABLE"
        out.evidence.append(
            ApiEvidence(endpoint=f"/v3/reference/tickers/{symbol}", status="ERROR", error=str(exc))
        )

    lineage: list[tuple[str, str | None]] = [(symbol, None)]
    try:
        events_payload = client.ticker_events(symbol)
        lineage = parse_ticker_lineage(symbol, events_payload)
        out.ticker_change_count = max(0, len({x[0] for x in lineage}) - 1)
        out.ticker_events_status = "AVAILABLE"
        out.evidence.append(
            ApiEvidence(
                endpoint=f"/vX/reference/tickers/{symbol}/events",
                status="OK",
                request_id=events_payload.get("request_id"),
            )
        )
    except Exception as exc:
        out.ticker_events_status = "UNAVAILABLE"
        out.evidence.append(
            ApiEvidence(
                endpoint=f"/vX/reference/tickers/{symbol}/events",
                status="ERROR",
                error=str(exc),
            )
        )

    try:
        splits_payload = client.splits(symbol)
        out.split_count = len(splits_payload.get("results") or [])
        out.split_history_status = "AVAILABLE"
        out.evidence.append(
            ApiEvidence(
                endpoint=f"/stocks/v1/splits?ticker={symbol}",
                status="OK",
                request_id=splits_payload.get("request_id"),
            )
        )
    except Exception as exc:
        out.split_history_status = "UNAVAILABLE"
        out.evidence.append(
            ApiEvidence(
                endpoint=f"/stocks/v1/splits?ticker={symbol}",
                status="ERROR",
                error=str(exc),
            )
        )

    # Query current ticker plus any Polygon-declared ticker-change lineage segments independently.
    # We never concatenate predecessor and successor price series in this phase.
    unique_lineage = []
    seen = set()
    for ticker, event_date in lineage:
        if ticker in seen:
            continue
        seen.add(ticker)
        unique_lineage.append((ticker, event_date))

    for ticker, event_date in unique_lineage:
        relationship = "CURRENT_TICKER" if ticker == symbol else "DECLARED_PREDECESSOR_TICKER"
        seg = query_segment(client, ticker, relationship, event_date, end_date, warmup_sessions)
        out.segments.append(seg)

    current = next((s for s in out.segments if s.ticker == symbol), None)
    if current:
        out.current_ticker_first_observation = current.first_observation
        out.current_ticker_last_observation = current.last_observation
        out.current_ticker_first_replay_eligible_date = current.warmup_eligible_date
        out.current_ticker_history_status = current.history_status
        out.history_years_current_ticker = years_between(
            current.first_observation, current.last_observation
        )

    firsts = [s.first_observation for s in out.segments if s.first_observation]
    eligible_starts = [s.warmup_eligible_date for s in out.segments if s.warmup_eligible_date]
    lasts = [s.last_observation for s in out.segments if s.last_observation]
    if firsts:
        out.lineage_earliest_polygon_observation = min(firsts)
    if eligible_starts:
        out.lineage_earliest_replay_eligible_date = min(eligible_starts)
    if firsts and lasts:
        out.history_years_lineage_envelope = years_between(min(firsts), max(lasts))

    if out.ticker_change_count > 0:
        out.lifecycle_flags.append("TICKER_CHANGE_LINEAGE_PRESENT")
        out.blockers.append("LINEAGE_JOIN_REQUIRES_SEPARATE_CERTIFICATION")
    if out.split_count > 0:
        out.lifecycle_flags.append("SPLIT_HISTORY_PRESENT")
    if out.ticker_events_status != "AVAILABLE":
        out.lifecycle_flags.append("TICKER_EVENTS_UNAVAILABLE")
    if out.split_history_status != "AVAILABLE":
        out.lifecycle_flags.append("SPLIT_HISTORY_UNAVAILABLE")
    if out.current_ticker_first_observation:
        if out.current_ticker_first_observation == POLYGON_PROVIDER_HISTORY_FLOOR.isoformat():
            out.lifecycle_flags.append("OBSERVED_AT_POLYGON_PROVIDER_HISTORY_FLOOR")
        if out.list_date and out.current_ticker_first_observation > out.list_date:
            out.lifecycle_flags.append("FIRST_BAR_AFTER_REPORTED_LIST_DATE")
    else:
        out.blockers.append("NO_CURRENT_TICKER_POLYGON_AGGREGATE_HISTORY")

    if current and current.warmup_eligible_date:
        out.replay_eligibility = "ELIGIBLE_CURRENT_TICKER_WINDOW"
    elif current and current.first_observation:
        out.replay_eligibility = "INSUFFICIENT_WARMUP_IN_EARLIEST_RETURNED_WINDOW"
        out.blockers.append("CURRENT_TICKER_WARMUP_NOT_SATISFIED")
    else:
        out.replay_eligibility = "INELIGIBLE_NO_CURRENT_TICKER_HISTORY"

    # Important: ticker lineage is evidence only. Never join automatically.
    out.lineage_join_authorized = False
    return out

def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def write_csv(path: Path, rows: list[SymbolAuthority]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol",
        "asset_type",
        "name",
        "current_ticker_first_observation",
        "current_ticker_first_replay_eligible_date",
        "current_ticker_last_observation",
        "lineage_earliest_polygon_observation",
        "lineage_earliest_replay_eligible_date",
        "history_years_current_ticker",
        "history_years_lineage_envelope",
        "replay_eligibility",
        "current_ticker_history_status",
        "ticker_details_status",
        "ticker_events_status",
        "split_history_status",
        "active",
        "list_date",
        "delisted_utc",
        "primary_exchange",
        "ticker_change_count",
        "split_count",
        "lifecycle_flags",
        "blockers",
        "lineage_join_authorized",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            writer.writerow({
                k: (
                    "|".join(d[k]) if isinstance(d.get(k), list)
                    else d.get(k)
                )
                for k in fields
            })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=".",
        help="TradingPlatform root; used only to resolve files, never for DB access.",
    )
    ap.add_argument(
        "--universe",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    ap.add_argument(
        "--polygon-api-key-env",
        default="POLYGON_API_KEY",
        help="Environment variable containing the Polygon API key.",
    )
    ap.add_argument(
        "--polygon-base-url",
        default=DEFAULT_POLYGON_BASE_URL,
        help="Direct Polygon-compatible REST API base URL.",
    )
    ap.add_argument("--end-date", default=dt.date.today().isoformat())
    ap.add_argument("--warmup-sessions", type=int, default=DEFAULT_WARMUP_SESSIONS)
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--request-interval", type=float, default=0.05)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument(
        "--output-json",
        default="reports/m77_19_7_symbol_specific_polygon_history_authority.json",
    )
    ap.add_argument(
        "--output-csv",
        default="reports/m77_19_7_symbol_specific_polygon_history_authority.csv",
    )
    ap.add_argument(
        "--checkpoint-json",
        default="research_data/m77_19_7/polygon_symbol_history_checkpoint.json",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Resume from prior checkpoint; only symbols with complete current-ticker history are reused.",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    universe = Path(args.universe)
    if not universe.is_absolute():
        universe = root / universe
    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = root / output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute():
        output_csv = root / output_csv
    checkpoint = Path(args.checkpoint_json)
    if not checkpoint.is_absolute():
        checkpoint = root / checkpoint

    api_key = os.environ.get(args.polygon_api_key_env, "").strip()
    end_date = dt.date.fromisoformat(args.end_date)
    symbols = load_universe(universe)

    client = PolygonDirectClient(
        api_key=api_key,
        base_url=args.polygon_base_url,
        timeout=args.timeout,
        retries=args.retries,
        min_interval_seconds=args.request_interval,
    )

    completed: dict[str, SymbolAuthority] = {}
    if args.resume and checkpoint.exists():
        prior = load_json(checkpoint)
        for raw in prior.get("symbols") or []:
            try:
                segs = [TickerSegment(**x) for x in raw.pop("segments", [])]
                ev = [ApiEvidence(**x) for x in raw.pop("evidence", [])]
                item = SymbolAuthority(**raw, segments=segs, evidence=ev)
                if item.current_ticker_first_observation:
                    completed[item.symbol] = item
            except Exception:
                continue

    pending = [(s, a) for s, a in symbols if s not in completed]
    lock = threading.Lock()

    def persist_checkpoint() -> None:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": VERSION,
            "source": HISTORY_AUTHORITY_SOURCE,
            "polygon_base_url": args.polygon_base_url,
            "provider_history_floor": POLYGON_PROVIDER_HISTORY_FLOOR.isoformat(),
            "warmup_sessions": args.warmup_sessions,
            "symbols": [asdict(completed[k]) for k in sorted(completed)],
        }
        tmp = checkpoint.with_suffix(checkpoint.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        tmp.replace(checkpoint)

    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
        futs = {
            pool.submit(analyze_symbol, symbol, asset, client, end_date, args.warmup_sessions):
                symbol
            for symbol, asset in pending
        }
        for i, fut in enumerate(as_completed(futs), 1):
            symbol = futs[fut]
            try:
                result = fut.result()
            except Exception as exc:
                result = SymbolAuthority(
                    symbol=symbol,
                    replay_eligibility="QUERY_FAILED",
                    current_ticker_history_status="QUERY_FAILED",
                    blockers=[f"SYMBOL_QUERY_FAILED:{type(exc).__name__}:{exc}"],
                )
            with lock:
                completed[symbol] = result
                if i % 10 == 0 or i == len(futs):
                    persist_checkpoint()
            print(
                f"[{len(completed)}/{len(symbols)}] {symbol} "
                f"first={result.current_ticker_first_observation} "
                f"eligible={result.current_ticker_first_replay_eligible_date} "
                f"ticker_changes={result.ticker_change_count} "
                f"splits={result.split_count} "
                f"status={result.replay_eligibility}"
            )

    ordered = [completed[s] for s, _ in symbols if s in completed]
    write_csv(output_csv, ordered)

    statuses = Counter(x.replay_eligibility for x in ordered)
    history_failures = [
        x.symbol for x in ordered
        if x.current_ticker_history_status in ("QUERY_FAILED", "AGGREGATE_QUERY_FAILED", "UNQUERIED")
    ]
    lineage_present = [x.symbol for x in ordered if x.ticker_change_count > 0]
    split_present = [x.symbol for x in ordered if x.split_count > 0]
    provider_floor_symbols = [
        x.symbol for x in ordered
        if x.current_ticker_first_observation == POLYGON_PROVIDER_HISTORY_FLOOR.isoformat()
    ]

    authority_ready = len(ordered) == len(symbols) and not history_failures
    report = {
        "version": VERSION,
        "status": (
            "READY_FOR_SYMBOL_SPECIFIC_REPLAY_WINDOW_CLASSIFICATION"
            if authority_ready
            else "BLOCKED_POLYGON_HISTORY_AUTHORITY_INCOMPLETE"
        ),
        "governance": {
            "history_authority_source": HISTORY_AUTHORITY_SOURCE,
            "polygon_direct_query": True,
            "database_access": DATABASE_ACCESS,
            "price_history_table_used": False,
            "canonical_universe": str(universe),
            "production_authority_effect": PRODUCTION_AUTHORITY_EFFECT,
            "full_23_year_reconstruction_authorized": FULL_23_YEAR_RECONSTRUCTION_AUTHORIZED,
            "symbol_specific_reconstruction_authorized": False,
            "ticker_lineage_join_authorized": False,
            "predecessor_successor_series_automatically_concatenated": False,
        },
        "polygon_query_contract": {
            "base_url": args.polygon_base_url,
            "aggregate_endpoint": "/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}",
            "from": POLYGON_PROVIDER_HISTORY_FLOOR.isoformat(),
            "to": end_date.isoformat(),
            "adjusted": True,
            "first_sort": "asc",
            "first_limit": EARLIEST_BAR_QUERY_LIMIT,
            "last_sort": "desc",
            "last_limit": 1,
            "ticker_details_endpoint": "/v3/reference/tickers/{ticker}",
            "ticker_events_endpoint": "/vX/reference/tickers/{ticker}/events",
            "splits_endpoint": "/stocks/v1/splits",
            "warmup_sessions": args.warmup_sessions,
        },
        "universe_symbol_count": len(symbols),
        "materialized_symbol_count": len(ordered),
        "replay_eligibility_counts": dict(statuses),
        "history_failure_count": len(history_failures),
        "history_failure_symbols": history_failures,
        "ticker_change_lineage_symbol_count": len(lineage_present),
        "ticker_change_lineage_symbols": lineage_present,
        "split_history_symbol_count": len(split_present),
        "provider_history_floor_symbol_count": len(provider_floor_symbols),
        "provider_history_floor_symbols": provider_floor_symbols,
        "symbol_specific_history_authority_ready": authority_ready,
        "symbols": [asdict(x) for x in ordered],
        "next_step": (
            "BUILD_M77_19_7_1_LIFECYCLE_LINEAGE_CLASSIFICATION_AND_REPLAY_WINDOW_AUTHORITY"
            if authority_ready
            else "RESOLVE_M77_19_7_POLYGON_HISTORY_AUTHORITY_BLOCKERS"
        ),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    persist_checkpoint()

    print()
    print("=== M77.19.7 SYMBOL-SPECIFIC POLYGON HISTORICAL AVAILABILITY & LIFECYCLE AUTHORITY ===")
    print("status:", report["status"])
    print("history_authority_source:", HISTORY_AUTHORITY_SOURCE)
    print("polygon_direct_query: True")
    print("database_access: NONE")
    print("price_history_table_used: False")
    print("universe_symbol_count:", len(symbols))
    print("materialized_symbol_count:", len(ordered))
    print("replay_eligibility_counts:", dict(statuses))
    print("ticker_change_lineage_symbol_count:", len(lineage_present))
    print("split_history_symbol_count:", len(split_present))
    print("history_failure_count:", len(history_failures))
    print("symbol_specific_history_authority_ready:", authority_ready)
    print("full_23_year_reconstruction_authorized: False")
    print("symbol_specific_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("json_report:", output_json)
    print("csv_report:", output_csv)
    print("checkpoint:", checkpoint)
    return 0 if authority_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
