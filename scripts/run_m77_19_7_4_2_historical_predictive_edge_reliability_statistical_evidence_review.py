#!/usr/bin/env python3
"""
M77.19.7.4.2 — Historical Predictive Edge, Reliability & Statistical Evidence Review

Research-only evidence decomposition over the completed M77.19.7.4.1 outcome
artifacts. This milestone DOES NOT change, tune, fit, calibrate, optimize, or
publish any production model behavior.

Evidence domains:
- native direction-strength taxonomy
- bullish / bearish asymmetry
- fixed confidence-bin reliability
- fixed overall-score-bin reliability
- naïve directional baselines
- fixed historical eras
- cross-sectional symbol stability
- economic magnitude / directional payoff
- symbol-cluster bootstrap uncertainty
- calendar-year block-bootstrap uncertainty

No Polygon API, database, price_history, StockIntelligence profile recompute,
threshold search, or parameter fitting is permitted.
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
import random
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION = "M77.19.7.4.2.4-REPAIRED-FULL-PROFILE-PROVENANCE-REPIN-1.0"
EXPECTED_OUTCOME_VERSION = "M77.19.7.4.1.2-REPAIRED-FULL-PROFILE-AUTHORITY-REPIN-1.0"
EXPECTED_OUTCOME_REPORT_SHA256 = "d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_PROFILE_AUTHORITY_SHA256 = "0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_REPLAY_AUTHORITY_VERSION = "M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
DEFAULT_REPLAY_AUTHORITY_JSON = "reports/m77_19_7_3_1_native_profile_schema_authority_repair.json"
EXPECTED_CERTIFIED_SYMBOL_COUNT = 602
EXPECTED_BLOCKED_SYMBOL_COUNT = 9
EXPECTED_REPLAYED_PROFILE_COUNT = 556283
EXPECTED_NATIVE_NOT_ELIGIBLE_COUNT = 1386
FIXED_HORIZONS = (5, 10, 20)
FIXED_CONFIDENCE_BINS = ((0,20),(20,40),(40,60),(60,80),(80,100))
FIXED_SCORE_BINS = ((0,20),(20,40),(40,60),(60,80),(80,100))
FIXED_ERAS = (
    ("2003-2007", 2003, 2007),
    ("2008-2012", 2008, 2012),
    ("2013-2017", 2013, 2017),
    ("2018-2022", 2018, 2022),
    ("2023-2026", 2023, 2026),
)
FIXED_SYMBOL_ACCURACY_BANDS = (
    ("LT_45", None, 0.45),
    ("45_TO_50", 0.45, 0.50),
    ("50_TO_55", 0.50, 0.55),
    ("GT_EQ_55", 0.55, None),
)
BOOTSTRAP_REPLICATIONS = 1000
BOOTSTRAP_SEED = 7719742

class EvidenceError(RuntimeError):
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


def load_replay_source_authority(
    project_root: Path,
    replay_authority_json: str | Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = resolve_project_path(project_root, replay_authority_json)
    if not path.is_file():
        raise EvidenceError(f"M77.19.7.3.1 replay authority missing: {path}")
    if sha256_file(path) != EXPECTED_PROFILE_AUTHORITY_SHA256:
        raise EvidenceError(
            "M77.19.7.3.1 replay authority SHA mismatch; refusing unpinned provenance"
        )
    with path.open("r", encoding="utf-8") as fh:
        authority = json.load(fh)
    if authority.get("version") != EXPECTED_REPLAY_AUTHORITY_VERSION:
        raise EvidenceError(
            f"unexpected replay authority version: {authority.get('version')!r}"
        )
    if authority.get("status") != "READY":
        raise EvidenceError("M77.19.7.3.1 replay authority is not READY")
    if authority.get("successful_symbol_cadence_replay_count") != EXPECTED_CERTIFIED_SYMBOL_COUNT:
        raise EvidenceError("M77.19.7.3.1 replay symbol count mismatch")
    if authority.get("failed_symbol_cadence_replay_count") != 0:
        raise EvidenceError("M77.19.7.3.1 replay authority contains failures")

    by_symbol: dict[str, dict[str, Any]] = {}
    for row in authority.get("symbols") or []:
        if row.get("cadence") != "WEEKLY":
            continue
        if row.get("status") != "REPLAYED_POINT_IN_TIME":
            continue
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            raise EvidenceError("replay authority row missing symbol")
        if symbol in by_symbol:
            raise EvidenceError(f"duplicate replay authority symbol: {symbol}")
        by_symbol[symbol] = row

    if len(by_symbol) != EXPECTED_CERTIFIED_SYMBOL_COUNT:
        raise EvidenceError(
            f"expected {EXPECTED_CERTIFIED_SYMBOL_COUNT} replay source records, "
            f"got {len(by_symbol)}"
        )
    return authority, by_symbol


def resolve_frozen_source_from_replay_authority(
    project_root: Path,
    outcome_symbol_meta: dict[str, Any],
    replay_symbol_meta: dict[str, Any],
) -> Path:
    symbol = str(outcome_symbol_meta.get("symbol") or "").strip()
    replay_symbol = str(replay_symbol_meta.get("symbol") or "").strip()
    if not symbol or symbol != replay_symbol:
        raise EvidenceError(
            f"source provenance symbol mismatch: outcome={symbol!r} replay={replay_symbol!r}"
        )

    outcome_sha = outcome_symbol_meta.get("source_data_sha256")
    replay_sha = replay_symbol_meta.get("source_data_sha256")
    if not outcome_sha or not replay_sha or outcome_sha != replay_sha:
        raise EvidenceError(
            f"{symbol}: source_data_sha256 mismatch between M77.19.7.4.1 and M77.19.7.3.1"
        )

    raw_path = replay_symbol_meta.get("source_data_file")
    if raw_path is None or not str(raw_path).strip():
        raise EvidenceError(f"{symbol}: replay authority missing source_data_file")

    source_path = resolve_project_path(project_root, str(raw_path).strip())
    if not source_path.is_file():
        raise EvidenceError(
            f"{symbol}: replay-authority source_data_file is not a regular file: {source_path}"
        )

    actual_sha = sha256_file(source_path)
    if actual_sha != replay_sha:
        raise EvidenceError(
            f"{symbol}: frozen source SHA mismatch: expected={replay_sha} actual={actual_sha}"
        )
    return source_path


def fixed_bin_label(lo: int | float, hi: int | float) -> str:
    return f"{int(lo)}-{int(hi)}"

def confidence_bin(x: float) -> str:
    if not 0.0 <= x <= 100.0:
        raise EvidenceError(f"confidence outside 0..100: {x}")
    for lo, hi in FIXED_CONFIDENCE_BINS:
        if lo <= x < hi or (hi == 100 and x == 100):
            return fixed_bin_label(lo, hi)
    raise EvidenceError(f"unbinnable confidence {x}")

def score_bin(x: float) -> str:
    if not 0.0 <= x <= 100.0:
        raise EvidenceError(f"overall_score outside 0..100: {x}")
    for lo, hi in FIXED_SCORE_BINS:
        if lo <= x < hi or (hi == 100 and x == 100):
            return fixed_bin_label(lo, hi)
    raise EvidenceError(f"unbinnable overall_score {x}")

def polarity(native_direction: str) -> str:
    s = str(native_direction).strip().upper()
    if s.endswith("_BULLISH") or s == "BULLISH":
        return "BULLISH"
    if s.endswith("_BEARISH") or s == "BEARISH":
        return "BEARISH"
    if s.endswith("_NEUTRAL") or s in {"NEUTRAL","FLAT","SIDEWAYS","MIXED"}:
        return "NEUTRAL"
    raise EvidenceError(f"unknown native direction: {native_direction!r}")

def era_label(year: int) -> str:
    for label, start, end in FIXED_ERAS:
        if start <= year <= end:
            return label
    raise EvidenceError(f"year outside fixed evidence eras: {year}")

def symbol_accuracy_band(acc: float) -> str:
    for label, lo, hi in FIXED_SYMBOL_ACCURACY_BANDS:
        if (lo is None or acc >= lo) and (hi is None or acc < hi):
            return label
    raise EvidenceError(f"unclassifiable symbol accuracy {acc}")

def new_acc() -> dict[str, Any]:
    return {
        "count": 0,
        "matured_count": 0,
        "not_matured_count": 0,
        "directional_evaluable_count": 0,
        "directional_hit_count": 0,
        "bullish_count": 0,
        "bullish_hit_count": 0,
        "bearish_count": 0,
        "bearish_hit_count": 0,
        "neutral_count": 0,
        "always_bullish_hit_count": 0,
        "previous_period_evaluable_count": 0,
        "previous_period_hit_count": 0,
        "raw_return_sum": 0.0,
        "directional_return_sum": 0.0,
        "directional_returns": [],
        "favorable_directional_returns": [],
        "adverse_directional_returns": [],
    }

def add_observation(
    acc: dict[str, Any], direction: str, outcome: dict[str, Any],
    previous_period_correct: bool | None,
) -> None:
    acc["count"] += 1
    if outcome["status"] != "MATURED":
        acc["not_matured_count"] += 1
        return
    acc["matured_count"] += 1
    ret = float(outcome["forward_return"])
    acc["raw_return_sum"] += ret
    if ret > 0:
        acc["always_bullish_hit_count"] += 1

    p = polarity(direction)
    if p == "NEUTRAL":
        acc["neutral_count"] += 1
    else:
        acc["directional_evaluable_count"] += 1
        d_ret = ret if p == "BULLISH" else -ret
        correct = d_ret > 0.0
        if correct:
            acc["directional_hit_count"] += 1
            acc["favorable_directional_returns"].append(d_ret)
        else:
            acc["adverse_directional_returns"].append(d_ret)
        acc["directional_return_sum"] += d_ret
        acc["directional_returns"].append(d_ret)
        if p == "BULLISH":
            acc["bullish_count"] += 1
            if correct:
                acc["bullish_hit_count"] += 1
        else:
            acc["bearish_count"] += 1
            if correct:
                acc["bearish_hit_count"] += 1

    if previous_period_correct is not None:
        acc["previous_period_evaluable_count"] += 1
        if previous_period_correct:
            acc["previous_period_hit_count"] += 1

def ratio(n: float | int, d: float | int) -> float | None:
    return None if not d else float(n) / float(d)

def safe_mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None

def safe_median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None

def finalize(acc: dict[str, Any]) -> dict[str, Any]:
    fav = acc.pop("favorable_directional_returns")
    adv = acc.pop("adverse_directional_returns")
    d_rets = acc.pop("directional_returns")
    out = dict(acc)
    out["directional_accuracy"] = ratio(
        out["directional_hit_count"], out["directional_evaluable_count"]
    )
    out["bullish_accuracy"] = ratio(out["bullish_hit_count"], out["bullish_count"])
    out["bearish_accuracy"] = ratio(out["bearish_hit_count"], out["bearish_count"])
    out["always_bullish_accuracy"] = ratio(
        out["always_bullish_hit_count"], out["matured_count"]
    )
    out["previous_period_direction_accuracy"] = ratio(
        out["previous_period_hit_count"], out["previous_period_evaluable_count"]
    )
    out["edge_vs_random_50_50"] = (
        None if out["directional_accuracy"] is None else out["directional_accuracy"] - 0.5
    )
    out["edge_vs_always_bullish"] = (
        None if out["directional_accuracy"] is None or out["always_bullish_accuracy"] is None
        else out["directional_accuracy"] - out["always_bullish_accuracy"]
    )
    out["edge_vs_previous_period_direction"] = (
        None if out["directional_accuracy"] is None or out["previous_period_direction_accuracy"] is None
        else out["directional_accuracy"] - out["previous_period_direction_accuracy"]
    )
    out["mean_raw_forward_return"] = (
        out["raw_return_sum"] / out["matured_count"] if out["matured_count"] else None
    )
    out["mean_directional_return"] = (
        out["directional_return_sum"] / out["directional_evaluable_count"]
        if out["directional_evaluable_count"] else None
    )
    out["median_directional_return"] = safe_median(d_rets)
    out["mean_favorable_directional_return"] = safe_mean(fav)
    out["mean_adverse_directional_return"] = safe_mean(adv)
    out["payoff_ratio"] = (
        None
        if not fav or not adv or safe_mean(adv) == 0
        else safe_mean(fav) / abs(safe_mean(adv))
    )
    return out

def read_daily(path: Path) -> tuple[list[dt.date], list[float]]:
    dates, closes = [], []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        if not {"session_date","close"}.issubset(set(r.fieldnames or [])):
            raise EvidenceError(f"{path}: session_date/close missing")
        for row in r:
            d = dt.date.fromisoformat(row["session_date"])
            c = float(row["close"])
            if not math.isfinite(c) or c <= 0:
                raise EvidenceError(f"{path}:{d}: invalid close")
            dates.append(d); closes.append(c)
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise EvidenceError(f"{path}: daily dates not unique ascending")
    return dates, closes

def trailing_direction(
    date_to_index: dict[dt.date,int], closes: list[float], as_of: dt.date, horizon: int
) -> str | None:
    idx = date_to_index.get(as_of)
    if idx is None or idx - horizon < 0:
        return None
    ret = closes[idx] / closes[idx-horizon] - 1.0
    if ret > 0:
        return "BULLISH"
    if ret < 0:
        return "BEARISH"
    return None

def previous_period_correct(
    date_to_index: dict[dt.date,int], closes: list[float], as_of: dt.date,
    horizon: int, outcome: dict[str,Any],
) -> bool | None:
    if outcome["status"] != "MATURED":
        return None
    prev = trailing_direction(date_to_index, closes, as_of, horizon)
    if prev is None:
        return None
    ret = float(outcome["forward_return"])
    return (ret > 0) if prev == "BULLISH" else (ret < 0)

def read_outcomes(path: Path) -> Iterable[dict[str,Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise EvidenceError(f"{path}:{i}: invalid JSONL") from exc
            yield row

def validate_outcome_report(path: Path) -> dict[str,Any]:
    if sha256_file(path) != EXPECTED_OUTCOME_REPORT_SHA256:
        raise EvidenceError("M77.19.7.4.1.2 outcome authority report SHA mismatch")
    with path.open("r", encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("version") != EXPECTED_OUTCOME_VERSION:
        raise EvidenceError(f"unexpected M77.19.7.4.1 version: {d.get('version')!r}")
    if d.get("status") != "READY":
        raise EvidenceError("M77.19.7.4.1 outcome authority is not READY")
    if d.get("authority_sha256") != EXPECTED_PROFILE_AUTHORITY_SHA256:
        raise EvidenceError("M77.19.7.3.1 profile authority SHA mismatch")
    if d.get("successful_symbol_evaluation_count") != EXPECTED_CERTIFIED_SYMBOL_COUNT:
        raise EvidenceError("certified symbol count mismatch")
    if d.get("failed_symbol_evaluation_count") != 0:
        raise EvidenceError("outcome authority contains failed symbols")
    if d.get("blocked_symbol_carried_forward_count") != EXPECTED_BLOCKED_SYMBOL_COUNT:
        raise EvidenceError("blocked symbol count mismatch")
    if d.get("aggregate_replayed_profile_count") != EXPECTED_REPLAYED_PROFILE_COUNT:
        raise EvidenceError("replayed profile count mismatch")
    if d.get("aggregate_native_not_eligible_count") != EXPECTED_NATIVE_NOT_ELIGIBLE_COUNT:
        raise EvidenceError("native-not-eligible count mismatch")
    if tuple(d.get("forward_horizons_sessions") or ()) != FIXED_HORIZONS:
        raise EvidenceError("fixed horizon authority mismatch")
    g = d.get("governance") or {}
    required = {
        "database_access": "NONE",
        "polygon_api_queried": False,
        "price_history_table_used": False,
        "production_authority_effect": False,
        "profile_recomputation_performed": False,
        "future_bars_used_for_profile_construction": False,
        "future_bars_authorized_for_realized_outcome_labeling_only": True,
        "threshold_search_or_optimization": False,
        "parameter_fitting": False,
    }
    bad = [k for k,v in required.items() if g.get(k) != v]
    if bad:
        raise EvidenceError(f"upstream governance mismatch: {bad}")
    return d

def update_group(groups: dict[str,dict[int,dict[str,Any]]], key: str, h: int,
                 direction: str, outcome: dict[str,Any], prev_correct: bool|None) -> None:
    if key not in groups:
        groups[key] = {x:new_acc() for x in FIXED_HORIZONS}
    add_observation(groups[key][h], direction, outcome, prev_correct)

def bootstrap_accuracy(
    clusters: list[tuple[int,int]], reps: int, seed: int
) -> dict[str,Any]:
    # clusters = [(hits, evaluable), ...]
    valid = [(h,n) for h,n in clusters if n > 0]
    if not valid:
        return {"replications": reps, "cluster_count": 0, "estimate": None,
                "ci_95_lower": None, "ci_95_upper": None}
    estimate = sum(h for h,n in valid) / sum(n for h,n in valid)
    rng = random.Random(seed)
    vals = []
    k = len(valid)
    for _ in range(reps):
        hit = total = 0
        for _j in range(k):
            h,n = valid[rng.randrange(k)]
            hit += h; total += n
        vals.append(hit/total if total else float("nan"))
    vals = sorted(v for v in vals if math.isfinite(v))
    def q(p: float) -> float:
        if not vals:
            return float("nan")
        pos = p*(len(vals)-1)
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        if lo == hi:
            return vals[lo]
        w = pos-lo
        return vals[lo]*(1-w)+vals[hi]*w
    return {
        "replications": reps,
        "cluster_count": k,
        "estimate": estimate,
        "ci_95_lower": q(0.025),
        "ci_95_upper": q(0.975),
    }

def empty_finalized_accumulator() -> dict[str, Any]:
    """Return the canonical zero-evidence representation for a fixed bin."""
    return finalize(new_acc())


def materialize_fixed_bins(
    finalized_bins: dict[str, dict[str, Any]],
    bin_ranges: tuple[tuple[int, int], ...],
) -> dict[str, dict[str, Any]]:
    """
    Ensure every predeclared reliability bin is present, even if the historical
    sample contains zero observations in that bin.

    Empty bins are evidence, not errors: they remain in the report with zero
    counts and null accuracies/returns.
    """
    out: dict[str, dict[str, Any]] = {}
    for lo, hi in bin_ranges:
        label = fixed_bin_label(lo, hi)
        out[label] = finalized_bins.get(label, empty_finalized_accumulator())
    extras = sorted(set(finalized_bins) - set(out))
    if extras:
        raise EvidenceError(f"unexpected reliability bins outside fixed authority: {extras}")
    return out


def monotonic_reliability(
    finalized_bins: dict[str, dict[str, Any]],
    bin_ranges: tuple[tuple[int, int], ...],
) -> dict[str, Any]:
    fixed = materialize_fixed_bins(finalized_bins, bin_ranges)
    labels = [fixed_bin_label(lo, hi) for lo, hi in bin_ranges]
    vals = [
        (
            b,
            fixed[b]["directional_accuracy"],
            fixed[b]["directional_evaluable_count"],
        )
        for b in labels
    ]
    comparable = [(b, a, n) for b, a, n in vals if a is not None and n > 0]
    nondecreasing = all(
        comparable[i][1] <= comparable[i + 1][1]
        for i in range(len(comparable) - 1)
    )
    return {
        "all_fixed_bins": [
            {
                "bin": b,
                "directional_accuracy": fixed[b]["directional_accuracy"],
                "evaluable_count": fixed[b]["directional_evaluable_count"],
                "empty": fixed[b]["directional_evaluable_count"] == 0,
            }
            for b in labels
        ],
        "comparable_nonempty_bins": [
            {"bin": b, "directional_accuracy": a, "evaluable_count": n}
            for b, a, n in comparable
        ],
        "empty_bin_count": sum(1 for b in labels if fixed[b]["directional_evaluable_count"] == 0),
        "nondecreasing_directional_accuracy": nondecreasing,
        "highest_bin_minus_lowest_bin_accuracy": (
            None if len(comparable) < 2 else comparable[-1][1] - comparable[0][1]
        ),
    }

def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--outcome-authority-json",
                    default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--replay-authority-json", default=DEFAULT_REPLAY_AUTHORITY_JSON)
    ap.add_argument("--output-json",
                    default="reports/m77_19_7_4_2_historical_predictive_edge_reliability_statistical_evidence_review.json")
    ap.add_argument("--output-csv",
                    default="reports/m77_19_7_4_2_symbol_horizon_evidence.csv")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    authority_path = resolve_project_path(project_root,args.outcome_authority_json)
    output_json = Path(args.output_json)
    if not output_json.is_absolute(): output_json = project_root/output_json
    output_csv = Path(args.output_csv)
    if not output_csv.is_absolute(): output_csv = project_root/output_csv

    authority = validate_outcome_report(authority_path)
    replay_authority, replay_by_symbol = load_replay_source_authority(
        project_root, args.replay_authority_json
    )
    symbol_meta = authority.get("symbols") or []
    if len(symbol_meta) != EXPECTED_CERTIFIED_SYMBOL_COUNT:
        raise EvidenceError(f"expected 602 symbol evidence records, got {len(symbol_meta)}")

    overall = {h:new_acc() for h in FIXED_HORIZONS}
    by_native_direction: dict[str,dict[int,dict[str,Any]]] = {}
    by_polarity: dict[str,dict[int,dict[str,Any]]] = {}
    by_confidence: dict[str,dict[int,dict[str,Any]]] = {}
    by_score: dict[str,dict[int,dict[str,Any]]] = {}
    by_era: dict[str,dict[int,dict[str,Any]]] = {}
    by_symbol: dict[str,dict[int,dict[str,Any]]] = {}
    by_year: dict[int,dict[int,dict[str,Any]]] = {}
    symbol_asset_type: dict[str,str|None] = {}

    processed_rows = 0
    for sm in symbol_meta:
        symbol = sm["symbol"]
        symbol_asset_type[symbol] = sm.get("asset_type")
        outcome_path = resolve_project_path(project_root, sm["outcome_file"])
        replay_sm = replay_by_symbol.get(symbol)
        if replay_sm is None:
            raise EvidenceError(
                f"{symbol}: missing from M77.19.7.3.1 replay source authority"
            )
        source_path = resolve_frozen_source_from_replay_authority(
            project_root, sm, replay_sm
        )
        if not outcome_path.exists():
            raise EvidenceError(f"{symbol}: outcome file missing: {outcome_path}")
        if sha256_file(outcome_path) != sm["outcome_sha256"]:
            raise EvidenceError(f"{symbol}: outcome SHA mismatch")
        if sha256_file(source_path) != sm["source_data_sha256"]:
            raise EvidenceError(f"{symbol}: source daily SHA mismatch")

        dates,closes = read_daily(source_path)
        date_to_index = {d:i for i,d in enumerate(dates)}
        by_symbol[symbol] = {h:new_acc() for h in FIXED_HORIZONS}

        for row in read_outcomes(outcome_path):
            processed_rows += 1
            as_of = dt.date.fromisoformat(row["as_of"])
            native = str(row.get("native_direction") or row.get("direction")).strip().upper()
            pol = polarity(native)
            conf = float(row["confidence"]); score=float(row["overall_score"])
            cbin=confidence_bin(conf); sbin=score_bin(score)
            era=era_label(as_of.year)
            if as_of.year not in by_year:
                by_year[as_of.year] = {h:new_acc() for h in FIXED_HORIZONS}
            for h in FIXED_HORIZONS:
                outcome = row["outcomes"][str(h)]
                prev = previous_period_correct(date_to_index,closes,as_of,h,outcome)
                add_observation(overall[h],native,outcome,prev)
                add_observation(by_symbol[symbol][h],native,outcome,prev)
                add_observation(by_year[as_of.year][h],native,outcome,prev)
                update_group(by_native_direction,native,h,native,outcome,prev)
                update_group(by_polarity,pol,h,native,outcome,prev)
                update_group(by_confidence,cbin,h,native,outcome,prev)
                update_group(by_score,sbin,h,native,outcome,prev)
                update_group(by_era,era,h,native,outcome,prev)

    if processed_rows != EXPECTED_REPLAYED_PROFILE_COUNT:
        raise EvidenceError(
            f"processed outcome rows {processed_rows} != expected {EXPECTED_REPLAYED_PROFILE_COUNT}"
        )

    finalized_overall={str(h):finalize(overall[h]) for h in FIXED_HORIZONS}
    def finish_groups(groups):
        return {k:{str(h):finalize(v[h]) for h in FIXED_HORIZONS}
                for k,v in sorted(groups.items())}
    f_native=finish_groups(by_native_direction)
    f_polarity=finish_groups(by_polarity)
    f_conf=finish_groups(by_confidence)
    f_score=finish_groups(by_score)
    f_era=finish_groups(by_era)
    f_symbol=finish_groups(by_symbol)

    # Cross-sectional stability and bootstrap evidence.
    cross_section={}
    uncertainty={}
    for h in FIXED_HORIZONS:
        symbol_accs=[]
        bands=defaultdict(int)
        symbol_clusters=[]
        for sym in sorted(f_symbol):
            x=f_symbol[sym][str(h)]
            if x["directional_accuracy"] is not None:
                symbol_accs.append(x["directional_accuracy"])
                bands[symbol_accuracy_band(x["directional_accuracy"])] += 1
                symbol_clusters.append((x["directional_hit_count"],x["directional_evaluable_count"]))
        cross_section[str(h)]={
            "symbol_count_with_directional_evidence":len(symbol_accs),
            "unweighted_mean_symbol_accuracy":safe_mean(symbol_accs),
            "median_symbol_accuracy":safe_median(symbol_accs),
            "weighted_aggregate_accuracy":finalized_overall[str(h)]["directional_accuracy"],
            "accuracy_band_symbol_counts":dict(sorted(bands.items())),
        }
        year_clusters=[]
        for year in sorted(by_year):
            x=finalize(by_year[year][h])
            if x["directional_evaluable_count"]:
                year_clusters.append((x["directional_hit_count"],x["directional_evaluable_count"]))
        uncertainty[str(h)]={
            "symbol_cluster_bootstrap":bootstrap_accuracy(
                symbol_clusters,BOOTSTRAP_REPLICATIONS,BOOTSTRAP_SEED+h
            ),
            "calendar_year_block_bootstrap":bootstrap_accuracy(
                year_clusters,BOOTSTRAP_REPLICATIONS,BOOTSTRAP_SEED+100+h
            ),
            "nominal_binomial_independence_not_assumed":True,
        }

    # Materialize all fixed confidence/score bins even when zero historical
    # observations occupy a band. This keeps the evidence schema stable and
    # makes data absence explicit rather than exceptional.
    for lo, hi in FIXED_CONFIDENCE_BINS:
        label = fixed_bin_label(lo, hi)
        if label not in f_conf:
            f_conf[label] = {
                str(h): empty_finalized_accumulator() for h in FIXED_HORIZONS
            }
    for lo, hi in FIXED_SCORE_BINS:
        label = fixed_bin_label(lo, hi)
        if label not in f_score:
            f_score[label] = {
                str(h): empty_finalized_accumulator() for h in FIXED_HORIZONS
            }

    reliability={}
    for h in FIXED_HORIZONS:
        hconf={b:f_conf[b][str(h)] for b in sorted(f_conf)}
        hscore={b:f_score[b][str(h)] for b in sorted(f_score)}
        hconf_fixed = materialize_fixed_bins(hconf, FIXED_CONFIDENCE_BINS)
        hscore_fixed = materialize_fixed_bins(hscore, FIXED_SCORE_BINS)
        reliability[str(h)]={
            "confidence":monotonic_reliability(hconf_fixed, FIXED_CONFIDENCE_BINS),
            "overall_score":monotonic_reliability(hscore_fixed, FIXED_SCORE_BINS),
        }

    baseline={}
    for h in FIXED_HORIZONS:
        x=finalized_overall[str(h)]
        baseline[str(h)]={
            "model_directional_accuracy":x["directional_accuracy"],
            "random_50_50_accuracy":0.5,
            "always_bullish_accuracy":x["always_bullish_accuracy"],
            "buy_and_hold_positive_forward_return_frequency":x["always_bullish_accuracy"],
            "previous_period_direction_accuracy":x["previous_period_direction_accuracy"],
            "edge_vs_random_50_50":x["edge_vs_random_50_50"],
            "edge_vs_always_bullish":x["edge_vs_always_bullish"],
            "edge_vs_previous_period_direction":x["edge_vs_previous_period_direction"],
        }

    report={
        "version":VERSION,
        "status":"READY",
        "outcome_authority_version":authority.get("version"),
        "outcome_authority_sha256":sha256_file(authority_path),
        "profile_authority_sha256":authority.get("authority_sha256"),
        "replay_source_authority_version": replay_authority.get("version"),
        "replay_source_authority_sha256": EXPECTED_PROFILE_AUTHORITY_SHA256,
        "repair_scope": [
            "REPLAY_SOURCE_PROVENANCE_AUTHORITY_JOIN",
            "EMPTY_RELIABILITY_BIN_MATERIALIZATION",
        ],
        "successful_symbol_count":len(symbol_meta),
        "blocked_symbol_carried_forward_count":authority.get("blocked_symbol_carried_forward_count"),
        "aggregate_replayed_profile_count":processed_rows,
        "fixed_horizons_sessions":list(FIXED_HORIZONS),
        "overall":finalized_overall,
        "native_direction_strength_evidence":f_native,
        "direction_polarity_evidence":f_polarity,
        "confidence_bin_evidence":f_conf,
        "overall_score_bin_evidence":f_score,
        "era_stability_evidence":f_era,
        "cross_sectional_stability_evidence":cross_section,
        "naive_baseline_evidence":baseline,
        "reliability_evidence":reliability,
        "statistical_uncertainty":uncertainty,
        "symbol_evidence":f_symbol,
        "governance":{
            "database_access":"NONE",
            "polygon_api_queried":False,
            "price_history_table_used":False,
            "profile_recomputation_performed":False,
            "production_authority_effect":False,
            "model_parameters_changed":False,
            "threshold_search_or_optimization":False,
            "confidence_bin_search_or_optimization":False,
            "score_bin_search_or_optimization":False,
            "parameter_fitting":False,
            "calibrator_fitting":False,
            "future_bars_used_only_from_existing_m77_19_7_4_1_outcome_labels":True,
            "bootstrap_method_predeclared":True,
            "bootstrap_replications":BOOTSTRAP_REPLICATIONS,
            "bootstrap_seed":BOOTSTRAP_SEED,
            "symbol_cluster_bootstrap":True,
            "calendar_year_block_bootstrap":True,
            "nominal_observations_treated_as_independent":False,
        },
        "decision_gate":{
            "predictive_value_certified":False,
            "confidence_calibration_change_authorized":False,
            "score_calibration_change_authorized":False,
            "production_model_change_authorized":False,
            "next_step":"REVIEW_M77_19_7_4_2_EVIDENCE_BEFORE_ANY_CALIBRATION_OR_MODEL_CHANGE",
        },
    }
    atomic_json(output_json,report)

    output_csv.parent.mkdir(parents=True,exist_ok=True)
    with output_csv.open("w",newline="",encoding="utf-8") as fh:
        fields=["symbol","asset_type","horizon_sessions","directional_evaluable_count",
                "directional_hit_count","directional_accuracy","bullish_count","bullish_accuracy",
                "bearish_count","bearish_accuracy","neutral_count","always_bullish_accuracy",
                "previous_period_direction_accuracy","edge_vs_random_50_50",
                "edge_vs_always_bullish","edge_vs_previous_period_direction",
                "mean_directional_return","median_directional_return","payoff_ratio"]
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for sym in sorted(f_symbol):
            for h in FIXED_HORIZONS:
                x=f_symbol[sym][str(h)]
                w.writerow({"symbol":sym,"asset_type":symbol_asset_type.get(sym),
                            "horizon_sessions":h,**{k:x.get(k) for k in fields[3:]}})

    print("=== M77.19.7.4.2 HISTORICAL PREDICTIVE EDGE, RELIABILITY & STATISTICAL EVIDENCE REVIEW ===")
    print()
    print("status: READY")
    print(f"successful_symbol_count: {len(symbol_meta)}")
    print(f"aggregate_replayed_profile_count: {processed_rows}")
    for h in FIXED_HORIZONS:
        x=finalized_overall[str(h)]
        u=uncertainty[str(h)]
        print(
            f"horizon_{h}_sessions: model_accuracy={x['directional_accuracy']} "
            f"always_bullish={x['always_bullish_accuracy']} "
            f"previous_period={x['previous_period_direction_accuracy']} "
            f"mean_directional_return={x['mean_directional_return']} "
            f"payoff_ratio={x['payoff_ratio']}"
        )
        print(
            f"horizon_{h}_symbol_cluster_ci95="
            f"[{u['symbol_cluster_bootstrap']['ci_95_lower']}, "
            f"{u['symbol_cluster_bootstrap']['ci_95_upper']}]"
        )
        print(
            f"horizon_{h}_year_block_ci95="
            f"[{u['calendar_year_block_bootstrap']['ci_95_lower']}, "
            f"{u['calendar_year_block_bootstrap']['ci_95_upper']}]"
        )
        print(
            f"horizon_{h}_confidence_monotonic="
            f"{reliability[str(h)]['confidence']['nondecreasing_directional_accuracy']}"
        )
        print(
            f"horizon_{h}_score_monotonic="
            f"{reliability[str(h)]['overall_score']['nondecreasing_directional_accuracy']}"
        )
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_2_EVIDENCE_BEFORE_ANY_CALIBRATION_OR_MODEL_CHANGE")
    print(f"report: {output_json}")
    print(f"csv: {output_csv}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
