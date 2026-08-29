#!/usr/bin/env python3
"""
M77.19.7.4 — Symbol-Specific Historical Outcome & Calibration Evaluation

Research-only post-replay evaluation.

Authority chain:
  M77.19.7.2 frozen Polygon daily bars
      -> M77.19.7.3.1 point-in-time native Stock Intelligence profiles
      -> M77.19.7.4 realized forward outcome / reliability evaluation

Critical temporal rule:
Future bars are authorized ONLY to label realized outcomes after a frozen
point-in-time profile has already been produced. They are never supplied to
StockIntelligenceService, never used to rebuild a profile, and never used to
select/tune thresholds.

No Polygon API, database, price_history, production publication, or parameter
optimization is performed by this runner.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import statistics
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

VERSION = "M77.19.7.4.1.2-REPAIRED-FULL-PROFILE-AUTHORITY-REPIN-1.0"
EXPECTED_AUTHORITY_VERSION = "M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
EXPECTED_AUTHORITY_SHA256 = "0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_UPSTREAM_7_2_SHA256 = "8e92c45c46027865a0fd6336bdb0e548c4cccf453ff7c599cf98fc5ded5d607c"
EXPECTED_CERTIFIED_COUNT = 602
EXPECTED_BLOCKED_COUNT = 9
EXPECTED_AGGREGATE_OBSERVATIONS = 557669
EXPECTED_AGGREGATE_REPLAYED = 556283
EXPECTED_AGGREGATE_NATIVE_NOT_ELIGIBLE = 1386
DEFAULT_HORIZONS = (5, 10, 20)
ALLOWED_HORIZONS = (5, 10, 20)
CONFIDENCE_BINS = (
    (0.0, 20.0), (20.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 100.0),
)
SCORE_BINS = (
    (0.0, 20.0), (20.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 100.0),
)
BULLISH_LABELS = {"BULLISH", "STRONG_BULLISH", "BULL", "LONG", "POSITIVE"}
BEARISH_LABELS = {"BEARISH", "STRONG_BEARISH", "BEAR", "SHORT", "NEGATIVE"}
NEUTRAL_LABELS = {"NEUTRAL", "FLAT", "SIDEWAYS", "MIXED"}

class EvaluationError(RuntimeError):
    pass

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def resolve_project_path(project_root: Path, raw: str | Path) -> Path:
    p = Path(raw)
    if p.exists():
        return p
    # Reports contain canonical absolute project paths. Permit relocation while
    # preserving the path below known project roots.
    parts = p.parts
    for anchor in ("research_data", "reports", "data"):
        if anchor in parts:
            i = parts.index(anchor)
            candidate = project_root.joinpath(*parts[i:])
            if candidate.exists():
                return candidate
    if not p.is_absolute():
        candidate = project_root / p
        if candidate.exists():
            return candidate
    return p

def parse_float(v: Any, field: str) -> float:
    try:
        x = float(v)
    except Exception as exc:
        raise EvaluationError(f"{field}: not numeric: {v!r}") from exc
    if not math.isfinite(x):
        raise EvaluationError(f"{field}: non-finite value: {v!r}")
    return x

def normalize_direction(value: Any) -> str:
    s = str(value).strip().upper()
    if s in BULLISH_LABELS:
        return "BULLISH"
    if s in BEARISH_LABELS:
        return "BEARISH"
    if s in NEUTRAL_LABELS:
        return "NEUTRAL"
    raise EvaluationError(f"unknown native direction label: {value!r}")

def direction_outcome(direction: str, forward_return: float) -> tuple[bool, bool | None]:
    d = normalize_direction(direction)
    if d == "NEUTRAL":
        return False, None
    if d == "BULLISH":
        return True, forward_return > 0.0
    return True, forward_return < 0.0

def confidence_bin(value: float) -> str:
    x = parse_float(value, "confidence")
    if not 0.0 <= x <= 100.0:
        raise EvaluationError(f"confidence outside certified 0..100 domain: {x}")
    for lo, hi in CONFIDENCE_BINS:
        if lo <= x < hi or (hi == 100.0 and x == 100.0):
            return f"{int(lo)}-{int(hi)}"
    raise EvaluationError(f"unbinnable confidence: {x}")

def score_bin(value: float) -> str:
    x = parse_float(value, "overall_score")
    if not 0.0 <= x <= 100.0:
        raise EvaluationError(f"overall_score outside certified 0..100 domain: {x}")
    for lo, hi in SCORE_BINS:
        if lo <= x < hi or (hi == 100.0 and x == 100.0):
            return f"{int(lo)}-{int(hi)}"
    raise EvaluationError(f"unbinnable overall_score: {x}")

def read_daily_bars(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"session_date", "close"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise EvaluationError(f"{path}: required columns {sorted(required)} missing")
        for raw in reader:
            day = dt.date.fromisoformat(raw["session_date"])
            close = parse_float(raw.get("close"), f"{path}:{day}:close")
            if close <= 0:
                raise EvaluationError(f"{path}:{day}: non-positive close")
            rows.append({"date": day, "close": close})
    if not rows:
        raise EvaluationError(f"{path}: no daily bars")
    dates = [r["date"] for r in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise EvaluationError(f"{path}: session dates not unique ascending")
    return rows

def read_jsonl_gzip(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise EvaluationError(f"{path}:{line_no}: invalid JSONL") from exc
            if not isinstance(row, dict):
                raise EvaluationError(f"{path}:{line_no}: row is not an object")
            yield row

def write_jsonl_gzip_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    count = 0
    try:
        with gzip.open(tmp_name, "wt", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                fh.write("\n")
                count += 1
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return count

def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp_name, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

def validate_authority(authority_path: Path) -> dict[str, Any]:
    if sha256_file(authority_path) != EXPECTED_AUTHORITY_SHA256:
        raise EvaluationError(
            "M77.19.7.3.1 authority SHA256 mismatch; refusing unpinned replay authority"
        )
    with authority_path.open("r", encoding="utf-8") as fh:
        a = json.load(fh)
    checks = {
        "version": a.get("version") == EXPECTED_AUTHORITY_VERSION,
        "status": a.get("status") == "READY",
        "successful_count": a.get("successful_symbol_cadence_replay_count") == EXPECTED_CERTIFIED_COUNT,
        "failed_count": a.get("failed_symbol_cadence_replay_count") == 0,
        "blocked_count": a.get("blocked_symbol_carried_forward_count") == EXPECTED_BLOCKED_COUNT,
        "observations": a.get("aggregate_observation_count") == EXPECTED_AGGREGATE_OBSERVATIONS,
        "replayed": a.get("aggregate_replayed_profile_count") == EXPECTED_AGGREGATE_REPLAYED,
        "not_eligible": a.get("aggregate_native_not_eligible_count") == EXPECTED_AGGREGATE_NATIVE_NOT_ELIGIBLE,
        "upstream_sha": a.get("upstream_authority_sha256") == EXPECTED_UPSTREAM_7_2_SHA256,
    }
    g = a.get("governance") or {}
    governance_checks = {
        "database_access": g.get("database_access") == "NONE",
        "polygon_api_queried": g.get("polygon_api_queried") is False,
        "price_history_table_used": g.get("price_history_table_used") is False,
        "point_in_time_price_prefix_only": g.get("point_in_time_price_prefix_only") is True,
        "point_in_time_spy_calendar_prefix_only": g.get("point_in_time_spy_calendar_prefix_only") is True,
        "future_daily_bar_access_authorized": g.get("future_daily_bar_access_authorized") is False,
        "future_weekly_monthly_bar_access_authorized": g.get("future_weekly_monthly_bar_access_authorized") is False,
        "threshold_search_or_optimization": g.get("threshold_search_or_optimization") is False,
        "production_authority_effect": g.get("production_authority_effect") is False,
    }
    failed = [k for k, ok in {**checks, **governance_checks}.items() if not ok]
    if failed:
        raise EvaluationError(f"M77.19.7.3.1 authority validation failed: {failed}")
    if a.get("cadences") != ["WEEKLY"]:
        raise EvaluationError(f"expected WEEKLY-only replay authority, got {a.get('cadences')!r}")
    return a

def parse_horizons(raw: str) -> tuple[int, ...]:
    try:
        hs = tuple(int(x.strip()) for x in raw.split(",") if x.strip())
    except Exception as exc:
        raise EvaluationError("horizons must be comma-separated integers") from exc
    if hs != DEFAULT_HORIZONS:
        raise EvaluationError(
            f"M77.19.7.4 fixed evaluation horizons are {DEFAULT_HORIZONS}; got {hs}"
        )
    return hs

def forward_outcome(
    daily_rows: list[dict[str, Any]], date_to_index: dict[dt.date, int],
    as_of: dt.date, horizon: int,
) -> dict[str, Any]:
    idx = date_to_index.get(as_of)
    if idx is None:
        raise EvaluationError(f"as_of {as_of} missing from frozen source daily bars")
    target_idx = idx + horizon
    if target_idx >= len(daily_rows):
        return {
            "status": "OUTCOME_NOT_MATURED",
            "horizon_sessions": horizon,
            "base_date": as_of.isoformat(),
            "base_close": daily_rows[idx]["close"],
            "target_date": None,
            "target_close": None,
            "forward_return": None,
        }
    base = daily_rows[idx]["close"]
    target = daily_rows[target_idx]
    ret = target["close"] / base - 1.0
    return {
        "status": "MATURED",
        "horizon_sessions": horizon,
        "base_date": as_of.isoformat(),
        "base_close": base,
        "target_date": target["date"].isoformat(),
        "target_close": target["close"],
        "forward_return": ret,
    }

def new_accumulator() -> dict[str, Any]:
    return {
        "profile_count": 0, "matured_count": 0, "not_matured_count": 0,
        "directional_evaluable_count": 0, "directional_hit_count": 0,
        "returns": [], "bullish_count": 0, "bullish_hits": 0,
        "bearish_count": 0, "bearish_hits": 0, "neutral_count": 0,
    }

def update_accumulator(acc: dict[str, Any], direction: str, outcome: dict[str, Any]) -> None:
    acc["profile_count"] += 1
    if outcome["status"] != "MATURED":
        acc["not_matured_count"] += 1
        return
    acc["matured_count"] += 1
    ret = float(outcome["forward_return"])
    acc["returns"].append(ret)
    d = normalize_direction(direction)
    evaluable, correct = direction_outcome(d, ret)
    if d == "BULLISH":
        acc["bullish_count"] += 1
        if correct:
            acc["bullish_hits"] += 1
    elif d == "BEARISH":
        acc["bearish_count"] += 1
        if correct:
            acc["bearish_hits"] += 1
    else:
        acc["neutral_count"] += 1
    if evaluable:
        acc["directional_evaluable_count"] += 1
        if correct:
            acc["directional_hit_count"] += 1

def safe_ratio(n: int | float, d: int | float) -> float | None:
    return None if not d else float(n) / float(d)

def finalize_accumulator(acc: dict[str, Any]) -> dict[str, Any]:
    returns = acc.pop("returns")
    out = dict(acc)
    out["directional_accuracy"] = safe_ratio(
        out["directional_hit_count"], out["directional_evaluable_count"]
    )
    out["bullish_accuracy"] = safe_ratio(out["bullish_hits"], out["bullish_count"])
    out["bearish_accuracy"] = safe_ratio(out["bearish_hits"], out["bearish_count"])
    out["mean_forward_return"] = statistics.fmean(returns) if returns else None
    out["median_forward_return"] = statistics.median(returns) if returns else None
    return out

def evaluate_symbol(
    project_root: Path, output_root: Path, symbol_meta: dict[str, Any],
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    symbol = str(symbol_meta["symbol"])
    result_path = resolve_project_path(project_root, symbol_meta["result_file"])
    source_path = resolve_project_path(project_root, symbol_meta["source_data_file"])
    if not result_path.exists():
        raise EvaluationError(f"{symbol}: replay result missing: {result_path}")
    if not source_path.exists():
        raise EvaluationError(f"{symbol}: frozen source data missing: {source_path}")
    if sha256_file(result_path) != symbol_meta.get("result_sha256"):
        raise EvaluationError(f"{symbol}: replay result SHA mismatch")
    if sha256_file(source_path) != symbol_meta.get("source_data_sha256"):
        raise EvaluationError(f"{symbol}: source data SHA mismatch")

    daily = read_daily_bars(source_path)
    date_to_index = {r["date"]: i for i, r in enumerate(daily)}
    accs = {h: new_accumulator() for h in horizons}
    confidence_accs = {
        h: {f"{int(lo)}-{int(hi)}": new_accumulator() for lo, hi in CONFIDENCE_BINS}
        for h in horizons
    }
    score_accs = {
        h: {f"{int(lo)}-{int(hi)}": new_accumulator() for lo, hi in SCORE_BINS}
        for h in horizons
    }
    output_rows: list[dict[str, Any]] = []
    native_not_eligible_count = 0
    replayed_count = 0

    for row in read_jsonl_gzip(result_path):
        status = row.get("status")
        if status == "NOT_ELIGIBLE_NATIVE":
            native_not_eligible_count += 1
            continue
        if status != "REPLAYED":
            raise EvaluationError(f"{symbol}: unexpected replay-row status {status!r}")
        replayed_count += 1
        as_of = dt.date.fromisoformat(str(row["as_of"]))
        native_direction = str(row["direction"]).strip().upper()
        direction = normalize_direction(native_direction)
        score = parse_float(row["overall_score"], "overall_score")
        confidence = parse_float(row["confidence"], "confidence")
        cbin = confidence_bin(confidence)
        sbin = score_bin(score)

        enriched = {
            "symbol": symbol,
            "asset_type": symbol_meta.get("asset_type"),
            "cadence": symbol_meta.get("cadence"),
            "as_of": as_of.isoformat(),
            "native_direction": native_direction,
            "direction": direction,
            "overall_score": score,
            "confidence": confidence,
            "semantic_hash": row.get("semantic_hash"),
            "outcomes": {},
        }
        for h in horizons:
            outcome = forward_outcome(daily, date_to_index, as_of, h)
            if outcome["status"] == "MATURED":
                evaluable, correct = direction_outcome(direction, outcome["forward_return"])
                outcome["direction_evaluable"] = evaluable
                outcome["direction_correct"] = correct
            else:
                outcome["direction_evaluable"] = None
                outcome["direction_correct"] = None
            enriched["outcomes"][str(h)] = outcome
            update_accumulator(accs[h], direction, outcome)
            update_accumulator(confidence_accs[h][cbin], direction, outcome)
            update_accumulator(score_accs[h][sbin], direction, outcome)
        output_rows.append(enriched)

    if replayed_count != int(symbol_meta.get("replayed_profile_count", -1)):
        raise EvaluationError(
            f"{symbol}: replayed count mismatch {replayed_count} != "
            f"{symbol_meta.get('replayed_profile_count')}"
        )
    if native_not_eligible_count != int(symbol_meta.get("native_not_eligible_count", -1)):
        raise EvaluationError(
            f"{symbol}: native-not-eligible count mismatch {native_not_eligible_count} != "
            f"{symbol_meta.get('native_not_eligible_count')}"
        )

    outcome_file = output_root/"weekly/outcomes"/f"{symbol}.jsonl.gz"
    write_jsonl_gzip_atomic(outcome_file, output_rows)
    outcome_sha = sha256_file(outcome_file)
    return {
        "symbol": symbol,
        "asset_type": symbol_meta.get("asset_type"),
        "cadence": symbol_meta.get("cadence"),
        "status": "EVALUATED",
        "replayed_profile_count": replayed_count,
        "native_not_eligible_count": native_not_eligible_count,
        "source_data_sha256": symbol_meta.get("source_data_sha256"),
        "replay_result_sha256": symbol_meta.get("result_sha256"),
        "outcome_file": str(outcome_file),
        "outcome_sha256": outcome_sha,
        "horizons": {str(h): finalize_accumulator(accs[h]) for h in horizons},
        "confidence_reliability": {
            str(h): {b: finalize_accumulator(a) for b, a in bins.items()}
            for h, bins in confidence_accs.items()
        },
        "score_reliability": {
            str(h): {b: finalize_accumulator(a) for b, a in bins.items()}
            for h, bins in score_accs.items()
        },
    }

def merge_finalized(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    # Rebuild exact aggregate from additive fields plus the symbol outcome files
    # later for returns; caller supplies returns separately.
    keys = (
        "profile_count", "matured_count", "not_matured_count",
        "directional_evaluable_count", "directional_hit_count",
        "bullish_count", "bullish_hits", "bearish_count", "bearish_hits",
        "neutral_count",
    )
    total = {k: 0 for k in keys}
    for r in rows:
        h = r["horizons"][str(horizon)]
        for k in keys:
            total[k] += h[k]
    total["directional_accuracy"] = safe_ratio(
        total["directional_hit_count"], total["directional_evaluable_count"]
    )
    total["bullish_accuracy"] = safe_ratio(total["bullish_hits"], total["bullish_count"])
    total["bearish_accuracy"] = safe_ratio(total["bearish_hits"], total["bearish_count"])
    return total

def aggregate_reliability(
    symbol_results: list[dict[str, Any]], horizons: tuple[int, ...],
    field: str, bin_labels: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    additive = (
        "profile_count", "matured_count", "not_matured_count",
        "directional_evaluable_count", "directional_hit_count",
        "bullish_count", "bullish_hits", "bearish_count", "bearish_hits",
        "neutral_count",
    )
    for h in horizons:
        out[str(h)] = {}
        for b in bin_labels:
            a = {k: 0 for k in additive}
            weighted_return_sum = 0.0
            weighted_return_n = 0
            for sr in symbol_results:
                x = sr[field][str(h)][b]
                for k in additive:
                    a[k] += x[k]
                if x["mean_forward_return"] is not None and x["matured_count"]:
                    weighted_return_sum += x["mean_forward_return"] * x["matured_count"]
                    weighted_return_n += x["matured_count"]
            a["directional_accuracy"] = safe_ratio(
                a["directional_hit_count"], a["directional_evaluable_count"]
            )
            a["bullish_accuracy"] = safe_ratio(a["bullish_hits"], a["bullish_count"])
            a["bearish_accuracy"] = safe_ratio(a["bearish_hits"], a["bearish_count"])
            a["mean_forward_return"] = (
                weighted_return_sum / weighted_return_n if weighted_return_n else None
            )
            # Median is intentionally not pooled from symbol medians.
            a["median_forward_return"] = None
            out[str(h)][b] = a
    return out

def enrich_aggregate_returns(
    aggregate: dict[str, Any], symbol_results: list[dict[str, Any]],
    horizons: tuple[int, ...],
) -> None:
    for h in horizons:
        returns: list[float] = []
        for sr in symbol_results:
            with gzip.open(sr["outcome_file"], "rt", encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    o = row["outcomes"][str(h)]
                    if o["status"] == "MATURED":
                        returns.append(float(o["forward_return"]))
        aggregate[str(h)]["mean_forward_return"] = statistics.fmean(returns) if returns else None
        aggregate[str(h)]["median_forward_return"] = statistics.median(returns) if returns else None

def write_summary_csv(path: Path, symbol_results: list[dict[str, Any]], horizons: tuple[int, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol", "asset_type", "cadence", "horizon_sessions",
        "replayed_profile_count", "native_not_eligible_count",
        "matured_count", "not_matured_count",
        "directional_evaluable_count", "directional_hit_count",
        "directional_accuracy", "mean_forward_return", "median_forward_return",
        "bullish_count", "bullish_accuracy", "bearish_count", "bearish_accuracy",
        "neutral_count", "source_data_sha256", "replay_result_sha256",
        "outcome_sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for sr in sorted(symbol_results, key=lambda x: x["symbol"]):
            for h in horizons:
                x = sr["horizons"][str(h)]
                w.writerow({
                    "symbol": sr["symbol"], "asset_type": sr["asset_type"],
                    "cadence": sr["cadence"], "horizon_sessions": h,
                    "replayed_profile_count": sr["replayed_profile_count"],
                    "native_not_eligible_count": sr["native_not_eligible_count"],
                    "matured_count": x["matured_count"],
                    "not_matured_count": x["not_matured_count"],
                    "directional_evaluable_count": x["directional_evaluable_count"],
                    "directional_hit_count": x["directional_hit_count"],
                    "directional_accuracy": x["directional_accuracy"],
                    "mean_forward_return": x["mean_forward_return"],
                    "median_forward_return": x["median_forward_return"],
                    "bullish_count": x["bullish_count"],
                    "bullish_accuracy": x["bullish_accuracy"],
                    "bearish_count": x["bearish_count"],
                    "bearish_accuracy": x["bearish_accuracy"],
                    "neutral_count": x["neutral_count"],
                    "source_data_sha256": sr["source_data_sha256"],
                    "replay_result_sha256": sr["replay_result_sha256"],
                    "outcome_sha256": sr["outcome_sha256"],
                })

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument(
        "--authority-json",
        default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json",
    )
    ap.add_argument(
        "--output-root",
        default="research_data/m77_19_7_4/symbol_specific_historical_outcome_calibration_evaluation",
    )
    ap.add_argument("--horizons", default="5,10,20")
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument(
        "--output-json",
        default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json",
    )
    ap.add_argument(
        "--output-csv",
        default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.csv",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    authority_path = resolve_project_path(project_root, args.authority_json)
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = project_root / output_root
    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = project_root / output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute():
        output_csv = project_root / output_csv

    horizons = parse_horizons(args.horizons)
    authority = validate_authority(authority_path)
    symbols = [
        x for x in authority["symbols"]
        if x.get("status") == "REPLAYED_POINT_IN_TIME" and x.get("cadence") == "WEEKLY"
    ]
    if len(symbols) != EXPECTED_CERTIFIED_COUNT:
        raise EvaluationError(f"expected {EXPECTED_CERTIFIED_COUNT} replayed symbols, got {len(symbols)}")

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    workers = max(1, args.max_workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(evaluate_symbol, project_root, output_root, s, horizons): s["symbol"]
            for s in symbols
        }
        for fut in as_completed(future_map):
            symbol = future_map[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})

    results.sort(key=lambda x: x["symbol"])
    failures.sort(key=lambda x: x["symbol"])
    status = "READY" if not failures and len(results) == EXPECTED_CERTIFIED_COUNT else "INCOMPLETE"

    aggregate = {str(h): merge_finalized(results, h) for h in horizons}
    if results:
        enrich_aggregate_returns(aggregate, results, horizons)

    report = {
        "version": VERSION,
        "status": status,
        "authority_version": authority.get("version"),
        "authority_sha256": sha256_file(authority_path),
        "upstream_7_2_authority_sha256": authority.get("upstream_authority_sha256"),
        "history_source": "M77.19.7.2_POLYGON_DIRECT_MATERIALIZATION",
        "profile_source": "M77.19.7.3.1_POINT_IN_TIME_NATIVE_STOCK_INTELLIGENCE_REPLAY",
        "cadences": ["WEEKLY"],
        "forward_horizons_sessions": list(horizons),
        "successful_symbol_evaluation_count": len(results),
        "failed_symbol_evaluation_count": len(failures),
        "failures": failures,
        "blocked_symbol_carried_forward_count": authority.get("blocked_symbol_carried_forward_count"),
        "blocked_symbols": authority.get("blocked_symbols"),
        "aggregate_observation_count": authority.get("aggregate_observation_count"),
        "aggregate_replayed_profile_count": authority.get("aggregate_replayed_profile_count"),
        "aggregate_native_not_eligible_count": authority.get("aggregate_native_not_eligible_count"),
        "aggregate_outcome_evaluation": aggregate,
        "confidence_reliability": aggregate_reliability(
            results, horizons, "confidence_reliability",
            [f"{int(lo)}-{int(hi)}" for lo, hi in CONFIDENCE_BINS],
        ),
        "score_reliability": aggregate_reliability(
            results, horizons, "score_reliability",
            [f"{int(lo)}-{int(hi)}" for lo, hi in SCORE_BINS],
        ),
        "governance": {
            "database_access": "NONE",
            "polygon_api_queried": False,
            "price_history_table_used": False,
            "production_authority_effect": False,
            "profile_recomputation_performed": False,
            "repaired_full_profile_authority_sha256": EXPECTED_AUTHORITY_SHA256,
            "native_strong_direction_labels_preserved": True,
            "directional_polarity_derived_for_outcome_scoring_only": True,
            "point_in_time_profile_inputs_mutated": False,
            "future_bars_used_for_profile_construction": False,
            "future_bars_authorized_for_realized_outcome_labeling_only": True,
            "outcome_horizons_fixed_predeclared": True,
            "threshold_search_or_optimization": False,
            "parameter_fitting": False,
            "confidence_treated_as_certified_probability": False,
            "confidence_evaluation_mode": "EMPIRICAL_DIRECTIONAL_RELIABILITY_BY_FIXED_BIN",
            "score_evaluation_mode": "EMPIRICAL_OUTCOME_RELIABILITY_BY_FIXED_BIN",
            "unmatured_outcomes_counted_as_failures": False,
            "ticker_lineage_join_authorized": False,
            "predecessor_successor_series_automatically_concatenated": False,
        },
        "symbols": results,
        "output_root": str(output_root),
        "output_csv": str(output_csv),
        "next_step": (
            "REVIEW_M77_19_7_4_HISTORICAL_OUTCOME_AND_CALIBRATION_EVIDENCE"
            if status == "READY" else
            "COMPLETE_M77_19_7_4_SYMBOL_SPECIFIC_HISTORICAL_OUTCOME_AND_CALIBRATION_EVALUATION"
        ),
    }
    atomic_json(output_json, report)
    write_summary_csv(output_csv, results, horizons)

    print("=== M77.19.7.4 SYMBOL-SPECIFIC HISTORICAL OUTCOME & CALIBRATION EVALUATION ===")
    print()
    print(f"status: {status}")
    print(f"authority_sha256: {report['authority_sha256']}")
    print("history_source: M77.19.7.2 POLYGON DIRECT MATERIALIZATION")
    print("profile_source: M77.19.7.3.1 POINT-IN-TIME NATIVE STOCK INTELLIGENCE REPLAY")
    print("polygon_api_queried: False")
    print("price_history_table_used: False")
    print("database_access: NONE")
    print("production_authority_effect: False")
    print("profile_recomputation_performed: False")
    print("future_bars_used_for_profile_construction: False")
    print("future_bars_authorized_for_realized_outcome_labeling_only: True")
    print(f"forward_horizons_sessions: {list(horizons)}")
    print(f"successful_symbol_evaluation_count: {len(results)}")
    print(f"failed_symbol_evaluation_count: {len(failures)}")
    print(f"aggregate_replayed_profile_count: {report['aggregate_replayed_profile_count']}")
    print(f"aggregate_native_not_eligible_count: {report['aggregate_native_not_eligible_count']}")
    for h in horizons:
        x = aggregate[str(h)]
        print(
            f"horizon_{h}_sessions: matured={x['matured_count']} "
            f"not_matured={x['not_matured_count']} "
            f"directional_accuracy={x['directional_accuracy']}"
        )
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print(f"next_step: {report['next_step']}")
    print(f"report: {output_json}")
    print(f"csv: {output_csv}")
    print(f"output_root: {output_root}")
    return 0 if status == "READY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
