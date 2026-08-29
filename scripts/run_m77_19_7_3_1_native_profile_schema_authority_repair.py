#!/usr/bin/env python3
"""
M77.19.7.3 — Point-in-Time Symbol-Specific Stock Intelligence Replay

Execute the frozen native Stock Intelligence profile over the symbol-specific
Polygon histories materialized by M77.19.7.2.

Critical point-in-time rule:
  For every replay observation date, the native Stock Intelligence executor
  receives ONLY daily OHLCV rows whose session_date <= as_of and ONLY SPY
  session-calendar dates <= as_of. Future daily bars, future weekly/monthly
  closes, future structure levels and future calendar sessions therefore cannot
  enter the historical computation through this replay adapter.

Authority / governance:
- M77.19.7.2 report SHA is pinned.
- The native M77.19.6 replay runner SHA is pinned.
- The already materialized Polygon daily files are the sole OHLCV authority.
- No Polygon requests are made in this stage.
- price_history and all database access are prohibited.
- SPY's frozen Polygon daily materialization is the session-calendar authority.
- blocked M77.19.7.2 symbols are carried forward and never replayed.
- predecessor/successor ticker histories are never concatenated.
- scoring before each symbol's certified replay_start is prohibited.
- native warmup/history policy remains 300 / 750 rows.
- no thresholds, weights, semantics, ranking, or production authority change.

The runner supports DAILY, WEEKLY and MONTHLY observation cadences. WEEKLY is
recommended/default for the first long-history research pass because it matches
the established M77 historical evaluation cadence while keeping the evidence
volume tractable. DAILY remains available without changing semantics.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import math
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
EXPECTED_UPSTREAM_VERSION = "M77.19.7.2-SYMBOL-SPECIFIC-HISTORICAL-REPLAY-MATERIALIZATION-1.0"
EXPECTED_UPSTREAM_SHA256 = "8e92c45c46027865a0fd6336bdb0e548c4cccf453ff7c599cf98fc5ded5d607c"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_TOTAL_SYMBOL_COUNT = 611
EXPECTED_CERTIFIED_COUNT = 602
EXPECTED_BLOCKED_COUNT = 9
EXPECTED_WARMUP = 300
EXPECTED_HISTORY_ROWS = 750
EXPECTED_SPY_DATA_SHA256 = "12510d08659753b0a5c077687ab83be90fa2e9d24f5f3af6e829db989d4506c9"
SUPPORTED_CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
DEFAULT_CADENCES = ("WEEKLY",)
RESULT_FIELDS = (
    "symbol", "as_of", "cadence", "direction", "overall_score", "confidence",
    "semantic_hash", "input_row_count", "calendar_session_count", "profile",
)
NON_SEMANTIC_KEYS = {
    "id", "run_id", "replay_run_id", "snapshot_id", "state_id", "publication_id",
    "request_id", "trace_id", "correlation_id", "generated_at", "created_at",
    "updated_at", "published_at", "snapshot_timestamp", "computed_at",
    "calculated_at", "ingested_at", "uuid", "nonce",
}


class ReplayError(RuntimeError):
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


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
    os.replace(tmp, path)


def write_csv_atomic(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = {k: row.get(k) for k in fields}
            if isinstance(out.get("blockers"), list):
                out["blockers"] = "|".join(out["blockers"])
            w.writerow(out)
    os.replace(tmp, path)


def safe_symbol_filename(symbol: str) -> str:
    return urllib.parse.quote(symbol, safe="").replace("%", "_")


def jsonable(v: Any) -> Any:
    if is_dataclass(v):
        return jsonable(asdict(v))
    if isinstance(v, Mapping):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if hasattr(v, "value") and not isinstance(v, (str, bytes, int, float, bool)):
        try:
            return jsonable(v.value)
        except Exception:
            pass
    if hasattr(v, "__dict__") and not isinstance(v, type):
        try:
            return jsonable(vars(v))
        except Exception:
            pass
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
    return v


def semantic_projection(v: Any) -> Any:
    if isinstance(v, Mapping):
        out = {}
        for key, value in v.items():
            lk = str(key).lower()
            if (
                lk in NON_SEMANTIC_KEYS
                or lk.endswith("_uuid")
                or lk.endswith("_run_id")
                or lk.endswith("_snapshot_id")
                or lk.endswith("_generated_at")
                or lk.endswith("_created_at")
            ):
                continue
            out[str(key)] = semantic_projection(value)
        return out
    if isinstance(v, (list, tuple)):
        return [semantic_projection(x) for x in v]
    return jsonable(v)


def semantic_hash(v: Any) -> str:
    raw = json.dumps(
        semantic_projection(v), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lookup(mapping: Mapping[str, Any], *names: str) -> Any:
    low = {str(k).lower(): k for k in mapping}
    for name in names:
        k = low.get(name.lower())
        if k is not None:
            return mapping[k]
    return None


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def read_daily_bars(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            day = dt.date.fromisoformat(raw["session_date"])
            row = {
                "date": day,
                "open": parse_float(raw.get("open")),
                "high": parse_float(raw.get("high")),
                "low": parse_float(raw.get("low")),
                "close": parse_float(raw.get("close")),
                "volume": parse_float(raw.get("volume")),
            }
            if any(row[k] is None for k in ("open", "high", "low", "close")):
                raise ReplayError(f"{path}: null OHLC at {day}")
            rows.append(row)
    if not rows:
        raise ReplayError(f"{path}: no daily bars")
    dates = [r["date"] for r in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ReplayError(f"{path}: dates are not strictly unique ascending")
    if any(d.weekday() >= 5 for d in dates):
        raise ReplayError(f"{path}: weekend daily session detected")
    return rows


def parse_cadences(raw: str) -> tuple[str, ...]:
    values = tuple(x.strip().upper() for x in raw.split(",") if x.strip())
    if not values:
        raise ReplayError("At least one cadence is required")
    unknown = [x for x in values if x not in SUPPORTED_CADENCES]
    if unknown:
        raise ReplayError(f"Unsupported cadence(s): {unknown}")
    # Preserve requested order, remove duplicates.
    return tuple(dict.fromkeys(values))


def select_observation_dates(
    session_dates: Iterable[dt.date], replay_start: dt.date, replay_end: dt.date, cadence: str
) -> list[dt.date]:
    dates = [d for d in session_dates if replay_start <= d <= replay_end]
    if cadence == "DAILY":
        return dates
    if cadence == "WEEKLY":
        latest: dict[tuple[int, int], dt.date] = {}
        for d in dates:
            iso = d.isocalendar()
            latest[(iso.year, iso.week)] = d
        return sorted(latest.values())
    if cadence == "MONTHLY":
        latest_m: dict[tuple[int, int], dt.date] = {}
        for d in dates:
            latest_m[(d.year, d.month)] = d
        return sorted(latest_m.values())
    raise ReplayError(f"Unsupported cadence {cadence}")


def asof_prefix(rows: list[dict[str, Any]], as_of: dt.date) -> list[dict[str, Any]]:
    """Return a copy-free-ish prefix list containing no row after as_of."""
    # Rows are ascending; binary search avoids rescanning the full tail.
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid]["date"] <= as_of:
            lo = mid + 1
        else:
            hi = mid
    return rows[:lo]


def asof_session_set(spy_dates: list[dt.date], as_of: dt.date) -> set[dt.date]:
    # Explicit truncation is a governance invariant, not an optimization.
    return {d for d in spy_dates if d <= as_of}


def validate_upstream(authority: dict[str, Any], authority_path: Path) -> None:
    actual = sha256_file(authority_path)
    if actual != EXPECTED_UPSTREAM_SHA256:
        raise ReplayError(
            f"M77.19.7.2 authority SHA mismatch expected={EXPECTED_UPSTREAM_SHA256} actual={actual}"
        )
    if authority.get("version") != EXPECTED_UPSTREAM_VERSION:
        raise ReplayError(f"Unexpected upstream version {authority.get('version')!r}")
    if authority.get("status") != "READY":
        raise ReplayError("M77.19.7.2 authority is not READY")
    if authority.get("certified_symbol_materialized_count") != EXPECTED_CERTIFIED_COUNT:
        raise ReplayError("Unexpected certified materialized count")
    if authority.get("certified_symbol_materialization_failure_count") != 0:
        raise ReplayError("Upstream materialization contains failures")
    if authority.get("blocked_symbol_carried_forward_count") != EXPECTED_BLOCKED_COUNT:
        raise ReplayError("Unexpected blocked count")
    if len(authority.get("symbols") or []) != EXPECTED_TOTAL_SYMBOL_COUNT:
        raise ReplayError("Unexpected upstream symbol row count")
    g = authority.get("governance") or {}
    required = {
        "history_source": "POLYGON_DIRECT_REST_API",
        "polygon_direct_query": True,
        "price_history_table_used": False,
        "database_access": "NONE",
        "predecessor_successor_series_automatically_concatenated": False,
        "ticker_lineage_join_authorized": False,
        "replay_before_certified_start_authorized": False,
        "warmup_sessions_required": EXPECTED_WARMUP,
        "production_authority_effect": False,
        "full_23_year_reconstruction_authorized": False,
        "threshold_search_or_optimization": False,
    }
    for key, expected in required.items():
        if g.get(key) != expected:
            raise ReplayError(
                f"Upstream governance mismatch {key}: expected={expected!r} actual={g.get(key)!r}"
            )

    certified = [x for x in authority["symbols"] if x.get("materialization_status") == "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW"]
    blocked = [x for x in authority["symbols"] if x.get("materialization_status") == "CARRIED_FORWARD_BLOCKED_NO_POLYGON_MATERIALIZATION"]
    if len(certified) != EXPECTED_CERTIFIED_COUNT or len(blocked) != EXPECTED_BLOCKED_COUNT:
        raise ReplayError("Upstream materialized/blocked row classification mismatch")
    spy = next((x for x in certified if x.get("symbol") == "SPY"), None)
    if spy is None or spy.get("data_sha256") != EXPECTED_SPY_DATA_SHA256:
        raise ReplayError("SPY frozen Polygon materialization authority mismatch")


def import_native_runner(project_root: Path):
    path = project_root / NATIVE_RUNNER_REL
    if not path.exists():
        raise ReplayError(f"Native runner missing: {path}")
    actual = sha256_file(path)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise ReplayError(
            f"Native runner SHA mismatch expected={EXPECTED_NATIVE_RUNNER_SHA256} actual={actual}"
        )
    spec = importlib.util.spec_from_file_location("m77_19_6_native_for_1973", path)
    if spec is None or spec.loader is None:
        raise ReplayError("Cannot import native replay runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("call_profile", "StockIntelligenceService"):
        if not hasattr(module, name):
            raise ReplayError(f"Native runner missing required authority callable {name}")
    return module


def materialized_data_path(output_root: Path, symbol: str) -> Path:
    return output_root / "daily_bars" / f"{safe_symbol_filename(symbol)}.daily.csv.gz"


def verify_symbol_data(row: Mapping[str, Any], output_root: Path) -> Path:
    path = materialized_data_path(output_root, str(row["symbol"]))
    if not path.exists():
        raise ReplayError(f"{row['symbol']}: materialized Polygon daily file missing: {path}")
    actual = sha256_file(path)
    expected = row.get("data_sha256")
    if actual != expected:
        raise ReplayError(
            f"{row['symbol']}: daily data SHA mismatch expected={expected} actual={actual}"
        )
    return path


def replay_signature(
    upstream_sha: str, symbol_row: Mapping[str, Any], cadence: str,
) -> str:
    payload = {
        "upstream_sha256": upstream_sha,
        "native_runner_sha256": EXPECTED_NATIVE_RUNNER_SHA256,
        "symbol": symbol_row["symbol"],
        "source_data_sha256": symbol_row["data_sha256"],
        "replay_start": symbol_row["replay_start"],
        "replay_end": symbol_row["replay_end"],
        "cadence": cadence,
        "warmup": EXPECTED_WARMUP,
        "history_rows": EXPECTED_HISTORY_ROWS,
        "point_in_time_prefix_only": True,
        "spy_calendar_prefix_only": True,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def result_paths(replay_root: Path, symbol: str, cadence: str) -> tuple[Path, Path]:
    stem = safe_symbol_filename(symbol)
    base = replay_root / cadence.lower()
    return base / "profiles" / f"{stem}.jsonl.gz", base / "symbol_metadata" / f"{stem}.json"



def validate_full_profile_payload_file(data_path: Path) -> dict[str, int | bool]:
    """
    Validate that every REPLAYED row contains a component-complete native
    profile payload. This is required before a prior artifact may be resumed
    for a full-profile authority run.

    Metadata-only NOT_ELIGIBLE_NATIVE rows are allowed.
    """
    replayed = 0
    not_eligible = 0
    profile_rows = 0
    with gzip.open(data_path, "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise ReplayError(f"{data_path}:{i}: invalid JSONL") from exc
            status = row.get("status")
            if status == "NOT_ELIGIBLE_NATIVE":
                not_eligible += 1
                continue
            if status != "REPLAYED":
                raise ReplayError(f"{data_path}:{i}: unexpected replay row status {status!r}")
            replayed += 1
            profile = row.get("profile")
            if not isinstance(profile, Mapping):
                return {
                    "valid": False,
                    "replayed_rows": replayed,
                    "profile_rows": profile_rows,
                    "not_eligible_rows": not_eligible,
                    "first_invalid_line": i,
                }
            if "direction" not in profile or "timeframe_states" not in profile:
                return {
                    "valid": False,
                    "replayed_rows": replayed,
                    "profile_rows": profile_rows,
                    "not_eligible_rows": not_eligible,
                    "first_invalid_line": i,
                }
            profile_rows += 1
    return {
        "valid": replayed == profile_rows,
        "replayed_rows": replayed,
        "profile_rows": profile_rows,
        "not_eligible_rows": not_eligible,
        "first_invalid_line": 0,
    }


def maybe_resume(
    replay_root: Path,
    symbol_row: Mapping[str, Any],
    cadence: str,
    upstream_sha: str,
    keep_full_profile: bool,
) -> dict[str, Any] | None:
    data_path, meta_path = result_paths(replay_root, str(symbol_row["symbol"]), cadence)
    if not data_path.exists() or not meta_path.exists():
        return None
    try:
        meta = load_json(meta_path)
    except Exception:
        return None
    if meta.get("replay_signature") != replay_signature(upstream_sha, symbol_row, cadence):
        return None
    if meta.get("result_sha256") != sha256_file(data_path):
        return None
    if meta.get("status") != "REPLAYED_POINT_IN_TIME":
        return None

    # Critical M77.19.7.3.1.1 repair:
    # a full-profile run may not resume metadata-only artifacts.
    if keep_full_profile:
        if meta.get("full_profile_retained") is not True:
            return None
        validation = validate_full_profile_payload_file(data_path)
        if validation.get("valid") is not True:
            return None
        meta["full_profile_payload_verified"] = True
        meta["full_profile_payload_replayed_rows"] = int(validation["replayed_rows"])
        meta["full_profile_payload_profile_rows"] = int(validation["profile_rows"])
    else:
        meta["full_profile_payload_verified"] = False

    return dict(meta, resumed=True)


def write_jsonl_gzip_atomic(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str))
            fh.write("\n")
            count += 1
    os.replace(tmp, path)
    return count


def profile_mapping(profile: Any) -> dict[str, Any]:
    data = jsonable(profile)
    if not isinstance(data, Mapping):
        raise ReplayError("Native Stock Intelligence profile did not normalize to a mapping")
    return dict(data)



def extract_native_profile_authority(profile: Any) -> tuple[Any, float, float]:
    """
    Extract the replay comparison fields using the same schema authority
    established by the M77.19.6 native compare_profile contract:

      direction  = profile.direction
      score      = profile.scores.overall
      confidence = profile.confidence

    Do not guess alternative top-level score fields.
    """
    direction = getattr(profile, "direction", None)
    scores = getattr(profile, "scores", None)
    score = getattr(scores, "overall", None) if scores is not None else None
    confidence = getattr(profile, "confidence", None)

    if direction is None or score is None or confidence is None:
        raise ReplayError(
            "native profile missing certified schema fields "
            "direction/scores.overall/confidence"
        )
    return direction, float(score), float(confidence)


def replay_one_symbol_cadence(
    native: Any,
    symbol_row: Mapping[str, Any],
    source_root: Path,
    replay_root: Path,
    spy_dates: list[dt.date],
    cadence: str,
    upstream_sha: str,
    keep_full_profile: bool,
) -> dict[str, Any]:
    symbol = str(symbol_row["symbol"])
    source_path = verify_symbol_data(symbol_row, source_root)
    rows = read_daily_bars(source_path)
    replay_start = dt.date.fromisoformat(str(symbol_row["replay_start"]))
    replay_end = dt.date.fromisoformat(str(symbol_row["replay_end"]))
    if rows[0]["date"].isoformat() != symbol_row["materialization_start"]:
        raise ReplayError(f"{symbol}: first source bar is not materialization_start")
    if rows[-1]["date"].isoformat() != symbol_row["replay_end"]:
        raise ReplayError(f"{symbol}: last source bar is not replay_end")
    dates = [r["date"] for r in rows]
    if replay_start not in set(dates):
        raise ReplayError(f"{symbol}: replay_start absent from source data")
    replay_idx = dates.index(replay_start)
    if replay_idx + 1 < EXPECTED_WARMUP:
        raise ReplayError(f"{symbol}: fewer than {EXPECTED_WARMUP} sessions through replay_start")

    observation_dates = select_observation_dates(dates, replay_start, replay_end, cadence)
    if not observation_dates:
        raise ReplayError(f"{symbol}: no {cadence} replay observation dates")

    service = native.StockIntelligenceService()
    output_records: list[dict[str, Any]] = []
    not_eligible = 0
    for as_of in observation_dates:
        prefix = asof_prefix(rows, as_of)
        if prefix and prefix[-1]["date"] > as_of:
            raise ReplayError(f"{symbol} {as_of}: future price row leaked into prefix")
        calendar = asof_session_set(spy_dates, as_of)
        if calendar and max(calendar) > as_of:
            raise ReplayError(f"{symbol} {as_of}: future session leaked into SPY calendar")
        profile = native.call_profile(
            service, symbol, prefix, as_of, calendar, EXPECTED_WARMUP, EXPECTED_HISTORY_ROWS
        )
        if profile is None:
            not_eligible += 1
            output_records.append({
                "symbol": symbol,
                "as_of": as_of.isoformat(),
                "cadence": cadence,
                "status": "NOT_ELIGIBLE_NATIVE",
                "input_row_count": len(prefix),
                "calendar_session_count": len(calendar),
            })
            continue
        mapping = profile_mapping(profile)
        try:
            direction, score, confidence = extract_native_profile_authority(profile)
        except ReplayError as exc:
            raise ReplayError(f"{symbol} {as_of}: {exc}") from exc
        record = {
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "cadence": cadence,
            "status": "REPLAYED",
            "direction": jsonable(direction),
            "overall_score": score,
            "confidence": confidence,
            "semantic_hash": semantic_hash(mapping),
            "input_row_count": len(prefix),
            "calendar_session_count": len(calendar),
        }
        if keep_full_profile:
            record["profile"] = mapping
        output_records.append(record)

    data_path, meta_path = result_paths(replay_root, symbol, cadence)
    count = write_jsonl_gzip_atomic(data_path, output_records)
    result_sha = sha256_file(data_path)
    replayed = count - not_eligible
    meta = {
        "version": VERSION,
        "status": "REPLAYED_POINT_IN_TIME",
        "symbol": symbol,
        "asset_type": symbol_row.get("asset_type"),
        "cadence": cadence,
        "replay_signature": replay_signature(upstream_sha, symbol_row, cadence),
        "upstream_authority_sha256": upstream_sha,
        "source_history": "M77.19.7.2_POLYGON_DIRECT_MATERIALIZATION",
        "source_data_sha256": symbol_row.get("data_sha256"),
        "source_data_file": str(source_path),
        "replay_start": symbol_row.get("replay_start"),
        "replay_end": symbol_row.get("replay_end"),
        "observation_count": count,
        "replayed_profile_count": replayed,
        "native_not_eligible_count": not_eligible,
        "result_file": str(data_path),
        "result_sha256": result_sha,
        "point_in_time_price_prefix_only": True,
        "point_in_time_spy_calendar_prefix_only": True,
        "weekly_monthly_future_bar_leakage_authorized": False,
        "warmup_sessions": EXPECTED_WARMUP,
        "history_rows": EXPECTED_HISTORY_ROWS,
        "polygon_api_queried": False,
        "price_history_table_used": False,
        "database_access": "NONE",
        "predecessor_successor_series_automatically_concatenated": False,
        "production_authority_effect": False,
        "full_profile_retained": keep_full_profile,
        "full_profile_payload_verified": keep_full_profile,
        "full_profile_payload_replayed_rows": replayed if keep_full_profile else 0,
        "full_profile_payload_profile_rows": replayed if keep_full_profile else 0,
        "resumed": False,
    }
    write_json_atomic(meta_path, meta)
    return dict(meta, metadata_file=str(meta_path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument(
        "--authority-json",
        default="reports/m77_19_7_2_symbol_specific_historical_replay_materialization.json",
    )
    ap.add_argument(
        "--materialization-root",
        default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization",
    )
    ap.add_argument(
        "--output-root",
        default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay",
    )
    ap.add_argument(
        "--output-json",
        default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json",
    )
    ap.add_argument(
        "--output-csv",
        default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.csv",
    )
    ap.add_argument("--cadences", default=",".join(DEFAULT_CADENCES))
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--symbols", default=None, help="Diagnostic subset, comma-separated")
    ap.add_argument(
        "--summary-only",
        action="store_true",
        help="Do not retain the full native profile in each replay record; direction/score/confidence/hash remain.",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    authority_path = Path(args.authority_json)
    if not authority_path.is_absolute(): authority_path = root / authority_path
    materialization_root = Path(args.materialization_root)
    if not materialization_root.is_absolute(): materialization_root = root / materialization_root
    replay_root = Path(args.output_root)
    if not replay_root.is_absolute(): replay_root = root / replay_root
    output_json = Path(args.output_json)
    if not output_json.is_absolute(): output_json = root / output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute(): output_csv = root / output_csv

    authority = load_json(authority_path)
    validate_upstream(authority, authority_path)
    upstream_sha = sha256_file(authority_path)
    cadences = parse_cadences(args.cadences)
    native = import_native_runner(root)

    certified_rows = [
        x for x in authority["symbols"]
        if x.get("materialization_status") == "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW"
    ]
    blocked_rows = [
        x for x in authority["symbols"]
        if x.get("materialization_status") != "MATERIALIZED_CERTIFIED_CURRENT_TICKER_WINDOW"
    ]
    selected: set[str] | None = None
    if args.symbols:
        selected = {x.strip() for x in args.symbols.split(",") if x.strip()}
        unknown = selected - {x["symbol"] for x in certified_rows}
        if unknown:
            raise ReplayError(f"Requested symbols are not certified: {sorted(unknown)}")
        certified_rows = [x for x in certified_rows if x["symbol"] in selected]

    # Session calendar comes from the frozen direct-Polygon SPY artifact, never DB.
    spy_row = next(x for x in authority["symbols"] if x.get("symbol") == "SPY")
    spy_path = verify_symbol_data(spy_row, materialization_root)
    spy_rows = read_daily_bars(spy_path)
    spy_dates = [x["date"] for x in spy_rows]

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    tasks = []
    for row in certified_rows:
        for cadence in cadences:
            if args.resume:
                prior = maybe_resume(
                    replay_root, row, cadence, upstream_sha, not args.summary_only
                )
                if prior is not None:
                    records.append(prior)
                    continue
            tasks.append((row, cadence))

    if tasks:
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
            future_map = {
                pool.submit(
                    replay_one_symbol_cadence,
                    native, row, materialization_root, replay_root, spy_dates, cadence,
                    upstream_sha, not args.summary_only,
                ): (row, cadence)
                for row, cadence in tasks
            }
            done = 0
            total = len(future_map)
            for future in as_completed(future_map):
                row, cadence = future_map[future]
                symbol = row["symbol"]
                done += 1
                try:
                    meta = future.result()
                    records.append(meta)
                    print(
                        f"[{done}/{total}] {symbol} {cadence}: REPLAYED "
                        f"observations={meta['observation_count']} profiles={meta['replayed_profile_count']} "
                        f"not_eligible={meta['native_not_eligible_count']}"
                    )
                except Exception as exc:
                    failure = {
                        "symbol": symbol, "cadence": cadence, "status": "REPLAY_FAILED",
                        "error_type": type(exc).__name__, "error": str(exc)[:2000],
                    }
                    failures.append(failure)
                    print(f"[{done}/{total}] {symbol} {cadence}: FAILED {exc}", file=sys.stderr)

    records.sort(key=lambda x: (str(x.get("symbol")), str(x.get("cadence"))))
    complete_full_authority = selected is None
    expected_task_count = EXPECTED_CERTIFIED_COUNT * len(cadences) if complete_full_authority else len(certified_rows) * len(cadences)
    successful = sum(x.get("status") == "REPLAYED_POINT_IN_TIME" for x in records)
    status = "READY" if successful == expected_task_count and not failures else "INCOMPLETE"

    aggregate_observations = sum(int(x.get("observation_count") or 0) for x in records)
    aggregate_profiles = sum(int(x.get("replayed_profile_count") or 0) for x in records)
    aggregate_not_eligible = sum(int(x.get("native_not_eligible_count") or 0) for x in records)

    report = {
        "version": VERSION,
        "status": status,
        "upstream_authority_sha256": upstream_sha,
        "native_runner_sha256": EXPECTED_NATIVE_RUNNER_SHA256,
        "cadences": list(cadences),
        "full_authority_run": complete_full_authority,
        "certified_symbol_count_in_scope": len(certified_rows),
        "blocked_symbol_carried_forward_count": EXPECTED_BLOCKED_COUNT if complete_full_authority else 0,
        "successful_symbol_cadence_replay_count": successful,
        "failed_symbol_cadence_replay_count": len(failures),
        "aggregate_observation_count": aggregate_observations,
        "aggregate_replayed_profile_count": aggregate_profiles,
        "aggregate_native_not_eligible_count": aggregate_not_eligible,
        "governance": {
            "source_history": "M77.19.7.2_POLYGON_DIRECT_MATERIALIZATION",
            "polygon_api_queried": False,
            "price_history_table_used": False,
            "database_access": "NONE",
            "spy_session_calendar_source": "M77.19.7.2_FROZEN_POLYGON_SPY_DAILY_BARS",
            "spy_data_sha256": EXPECTED_SPY_DATA_SHA256,
            "point_in_time_price_prefix_only": True,
            "point_in_time_spy_calendar_prefix_only": True,
            "future_daily_bar_access_authorized": False,
            "future_weekly_monthly_bar_access_authorized": False,
            "replay_before_certified_start_authorized": False,
            "predecessor_successor_series_automatically_concatenated": False,
            "ticker_lineage_join_authorized": False,
            "native_warmup_sessions": EXPECTED_WARMUP,
            "native_history_rows": EXPECTED_HISTORY_ROWS,
            "native_runner_sha_pinned": True,
            "full_profile_resume_integrity_required": not args.summary_only,
            "metadata_only_resume_allowed_for_full_profile_run": False,
            "threshold_search_or_optimization": False,
            "production_authority_effect": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "symbols": records,
        "failures": failures,
        "blocked_symbols": blocked_rows if complete_full_authority else [],
        "output_root": str(replay_root),
        "next_step": (
            "BUILD_M77_19_7_4_SYMBOL_SPECIFIC_HISTORICAL_OUTCOME_AND_CALIBRATION_EVALUATION"
            if status == "READY" and complete_full_authority
            else "COMPLETE_M77_19_7_3_POINT_IN_TIME_SYMBOL_SPECIFIC_STOCK_INTELLIGENCE_REPLAY"
        ),
    }
    write_json_atomic(output_json, report)
    csv_rows = []
    for x in records:
        csv_rows.append({
            "symbol": x.get("symbol"), "asset_type": x.get("asset_type"), "cadence": x.get("cadence"),
            "status": x.get("status"), "replay_start": x.get("replay_start"), "replay_end": x.get("replay_end"),
            "observation_count": x.get("observation_count"), "replayed_profile_count": x.get("replayed_profile_count"),
            "native_not_eligible_count": x.get("native_not_eligible_count"), "source_data_sha256": x.get("source_data_sha256"),
            "result_sha256": x.get("result_sha256"), "resumed": x.get("resumed", False), "blockers": [],
        })
    for x in failures:
        csv_rows.append({
            "symbol": x.get("symbol"), "asset_type": None, "cadence": x.get("cadence"), "status": x.get("status"),
            "replay_start": None, "replay_end": None, "observation_count": None, "replayed_profile_count": None,
            "native_not_eligible_count": None, "source_data_sha256": None, "result_sha256": None, "resumed": False,
            "blockers": [x.get("error")],
        })
    write_csv_atomic(output_csv, sorted(csv_rows, key=lambda x: (str(x.get("symbol")), str(x.get("cadence")))), [
        "symbol", "asset_type", "cadence", "status", "replay_start", "replay_end", "observation_count",
        "replayed_profile_count", "native_not_eligible_count", "source_data_sha256", "result_sha256", "resumed", "blockers",
    ])

    print("=== M77.19.7.3.1 NATIVE PROFILE SCHEMA AUTHORITY REPAIR ===")
    print("status:", status)
    print("upstream_authority_sha256:", upstream_sha)
    print("native_runner_sha256_verified: True")
    print("history_source: M77.19.7.2 POLYGON DIRECT MATERIALIZATION")
    print("polygon_api_queried: False")
    print("price_history_table_used: False")
    print("database_access: NONE")
    print("spy_session_calendar: FROZEN POLYGON SPY DAILY BARS")
    print("cadences:", list(cadences))
    print("successful_symbol_cadence_replay_count:", successful)
    print("failed_symbol_cadence_replay_count:", len(failures))
    print("aggregate_observation_count:", aggregate_observations)
    print("aggregate_replayed_profile_count:", aggregate_profiles)
    print("aggregate_native_not_eligible_count:", aggregate_not_eligible)
    print("point_in_time_price_prefix_only: True")
    print("point_in_time_spy_calendar_prefix_only: True")
    print("future_weekly_monthly_bar_access_authorized: False")
    print("production_authority_effect: False")
    print("full_23_year_reconstruction_authorized: False")
    print("next_step:", report["next_step"])
    print("report:", output_json)
    print("csv:", output_csv)
    print("output_root:", replay_root)
    return 0 if status == "READY" or selected is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
