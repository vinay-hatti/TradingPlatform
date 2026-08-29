#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import importlib
import importlib.util
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.14-RESIDUAL-CANDIDATE-GENERATION-SEMANTICS-FORENSICS-1.0"

REPORT_5213_REL = "reports/m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.json"
EXPECTED_REPORT_5213_SHA256 = "10bdff010160faa49175c123907c9c8eb365739c547c95c679841355258c847e"

RUNNER_5213_REL = "scripts/run_m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.py"
EXPECTED_RUNNER_5213_SHA256 = "c3b5b27c4327f73e6767b1381ecca758eb8b1816e4f15bf57dbd9c9bade68892"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

PARITY_TOLERANCE = 1e-9
LEVEL_MERGE_THRESHOLD = 0.003
EXPECTED_NATIVE_MISSING = 67
EXPECTED_NO_TOP12_MISSING = 54
EXPECTED_RESTORED_BY_NO_TOP12 = 13

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def require_file(root: Path, rel: str, expected_sha: str, label: str) -> Path:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"FAIL CLOSED: required {label} missing: {rel}")
    actual = sha256_file(path)
    if actual != expected_sha:
        raise SystemExit(f"FAIL CLOSED: {label} SHA drift: expected={expected_sha} actual={actual}")
    return path

def import_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAIL CLOSED: unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def exact(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE

def rel_distance(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))

def level_price(x: Any) -> float:
    value = x.get("price") if isinstance(x, dict) else getattr(x, "price", None)
    if value is None:
        raise ValueError("level missing price")
    return float(value)

def level_timeframe(x: Any) -> str:
    value = x.get("timeframe") if isinstance(x, dict) else getattr(x, "timeframe", None)
    return str(value or "")

def serialize_level(x: Any) -> dict[str, Any]:
    if isinstance(x, dict):
        return copy.deepcopy(x)
    out = {}
    for field in (
        "level_type", "price", "timeframe", "strength", "confluence_score",
        "touch_count", "break_probability", "hold_probability", "metadata",
        "contributing_timeframes",
    ):
        if hasattr(x, field):
            out[field] = copy.deepcopy(getattr(x, field))
    return out

def validate_5213(report: dict[str, Any]) -> dict[str, Any]:
    summaries = report.get("arm_summaries") or {}
    native = summaries.get("NATIVE_CONTROL") or {}
    no_top12 = summaries.get("NO_TOP12_RETENTION") or {}
    winner = report.get("winner_analysis") or {}
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "winner_no_top12": winner.get("winner") == "NO_TOP12_RETENTION",
        "forensic_conclusion": report.get("forensic_conclusion")
            == "PREDECLARED_CANDIDATE_ALGORITHM_HYPOTHESIS_PARTIALLY_RESTORES_FROZEN_LEVEL_REACHABILITY",
        "native_missing_67": native.get("combined_missing_beyond_0_3pct_count") == EXPECTED_NATIVE_MISSING,
        "no_top12_missing_54": no_top12.get("combined_missing_beyond_0_3pct_count") == EXPECTED_NO_TOP12_MISSING,
        "restored_13": no_top12.get("combined_missing_reduction_vs_native") == EXPECTED_RESTORED_BY_NO_TOP12,
        "exact_tradeoff_minus_9": no_top12.get("combined_exact_gain_vs_native") == -9,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.13 authority validation failed: {checks}")
    return checks

@contextlib.contextmanager
def readonly_session():
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text
    session = SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
        session.rollback()
    finally:
        session.close()

def load_spy_sessions() -> set[dt.date]:
    from sqlalchemy import text
    with readonly_session() as session:
        rows = session.execute(text("""
            SELECT date
            FROM public.price_history
            WHERE symbol = 'SPY'
            ORDER BY date
        """)).all()
    out: set[dt.date] = set()
    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        out.add(value)
    if not out:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")
    return out

def row_date(row: Any) -> str:
    if isinstance(row, dict):
        for key in ("date", "timestamp", "datetime", "time"):
            if key in row:
                return str(row[key])[:10]
    for key in ("date", "timestamp", "datetime", "time"):
        if hasattr(row, key):
            return str(getattr(row, key))[:10]
    return ""

def row_num(row: Any, key: str):
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    try:
        return float(value)
    except Exception:
        return None

def candidate_stage_provenance(price: float, side: str, rows: list[Any]) -> dict[str, Any]:
    if not rows:
        return {
            "input_row_count": 0,
            "exact_side_ohlc_hits": [],
            "near_side_ohlc_hits": [],
            "qualifies_pivot_radius_2": False,
            "qualifies_rolling_window": [],
        }

    field = "low" if side == "support" else "high"
    exact_hits = []
    near_hits = []
    pivot_hits = []
    rolling_hits = []

    values = [row_num(r, field) for r in rows]
    for i, value in enumerate(values):
        if value is None:
            continue
        if exact(price, value):
            exact_hits.append({"index": i, "date": row_date(rows[i]), "value": value})
            if 2 <= i < len(rows) - 2:
                neighborhood = [v for v in values[i-2:i+3] if v is not None]
                qualifies = (
                    value <= min(neighborhood) if side == "support"
                    else value >= max(neighborhood)
                )
                if qualifies:
                    pivot_hits.append({"index": i, "date": row_date(rows[i]), "value": value})
        elif rel_distance(value, price) < LEVEL_MERGE_THRESHOLD:
            near_hits.append({
                "index": i,
                "date": row_date(rows[i]),
                "value": value,
                "relative_distance": rel_distance(value, price),
            })

    for w in (20, 50, 100):
        if len(rows) >= w:
            tail = [row_num(r, field) for r in rows[-w:]]
            tail = [v for v in tail if v is not None]
            if tail:
                extreme = min(tail) if side == "support" else max(tail)
                if exact(price, extreme):
                    rolling_hits.append(w)

    return {
        "input_row_count": len(rows),
        "input_start": row_date(rows[0]),
        "input_end": row_date(rows[-1]),
        "exact_side_ohlc_hits": exact_hits,
        "near_side_ohlc_hits": sorted(near_hits, key=lambda x: x["relative_distance"])[:5],
        "qualifies_pivot_radius_2": bool(pivot_hits),
        "pivot_hits": pivot_hits,
        "qualifies_rolling_window": rolling_hits,
    }

def capture_hypothesis_inputs(service: Any, hypothesis_analyze):
    capture = []
    def wrapped(timeframe, data):
        support, resistance = hypothesis_analyze(timeframe, data)
        input_rows = copy.deepcopy(list(data or []))
        capture.append({
            "timeframe": str(timeframe),
            "rows": input_rows,
            "support": copy.deepcopy(list(support or [])),
            "resistance": copy.deepcopy(list(resistance or [])),
        })
        return support, resistance
    service.levels.sr.analyze = wrapped
    return capture

def missing_frozen(frozen_items: list[Any], produced_items: list[Any]) -> list[Any]:
    produced = [level_price(x) for x in produced_items]
    return [
        x for x in frozen_items
        if not any(rel_distance(p, level_price(x)) < LEVEL_MERGE_THRESHOLD for p in produced)
    ]

def classify_residual(frozen_level: Any, side: str, capture: list[dict[str, Any]]) -> dict[str, Any]:
    fp = level_price(frozen_level)
    frozen_tf = level_timeframe(frozen_level)

    by_tf = {block["timeframe"]: block for block in capture}
    tf_block = by_tf.get(frozen_tf)
    tf_rows = list((tf_block or {}).get("rows") or [])
    tf_prov = candidate_stage_provenance(fp, side, tf_rows)

    all_prov = {}
    any_exact = False
    any_near = False
    any_pre_candidate = False
    nearest_generated = None
    nearest_generated_tf = None

    for block in capture:
        tf = block["timeframe"]
        prov = candidate_stage_provenance(fp, side, list(block.get("rows") or []))
        all_prov[tf] = prov
        any_exact = any_exact or bool(prov["exact_side_ohlc_hits"])
        any_near = any_near or bool(prov["near_side_ohlc_hits"])
        any_pre_candidate = any_pre_candidate or bool(
            prov["qualifies_pivot_radius_2"] or prov["qualifies_rolling_window"]
        )

        for item in block[side]:
            dist = rel_distance(level_price(item), fp)
            if nearest_generated is None or dist < nearest_generated:
                nearest_generated = dist
                nearest_generated_tf = tf

    if frozen_tf and tf_block is not None and len(tf_rows) < 20:
        classification = "FROZEN_TIMEFRAME_NATIVE_INELIGIBLE_LT20"
    elif tf_prov["qualifies_pivot_radius_2"] or tf_prov["qualifies_rolling_window"]:
        classification = "FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE"
    elif tf_prov["exact_side_ohlc_hits"]:
        classification = "FROZEN_TIMEFRAME_OHLC_EXACT_BUT_NATIVE_SELECTION_EXCLUDES"
    elif any_pre_candidate:
        classification = "CROSS_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_PROVENANCE"
    elif any_exact:
        classification = "CROSS_TIMEFRAME_OHLC_EXACT_PROVENANCE_ONLY"
    elif any_near:
        classification = "NEAR_CAPTURED_OHLC_WITHOUT_EXACT_PROVENANCE"
    else:
        classification = "NO_CAPTURED_OHLC_PROVENANCE"

    return {
        "side": side,
        "frozen_level": serialize_level(frozen_level),
        "frozen_price": fp,
        "frozen_timeframe": frozen_tf,
        "classification": classification,
        "frozen_timeframe_provenance": tf_prov,
        "all_timeframe_provenance": all_prov,
        "nearest_generated_candidate_relative_distance": nearest_generated,
        "nearest_generated_candidate_timeframe": nearest_generated_tf,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = ((root / args.bundle_root).resolve()
                   if not Path(args.bundle_root).is_absolute() else Path(args.bundle_root))
    output = ((root / args.output).resolve()
              if not Path(args.output).is_absolute() else Path(args.output))

    report5213_path = require_file(root, REPORT_5213_REL, EXPECTED_REPORT_5213_SHA256,
                                   "M77.19.6.5.2.13 report")
    runner5213_path = require_file(root, RUNNER_5213_REL, EXPECTED_RUNNER_5213_SHA256,
                                   "M77.19.6.5.2.13.1 runner")
    runner529_path = require_file(root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256,
                                  "M77.19.6.5.2.9.1 runner")
    native_path = require_file(root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256,
                               "native replay runner")

    report5213 = load_json(report5213_path)
    authority5213 = validate_5213(report5213)

    helper5213 = import_module_from_path(runner5213_path, "m77_helper_5213_for_5214")
    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5214")
    native = import_module_from_path(native_path, "m77_native_5214")
    if not hasattr(helper529, "normalize_rows"):
        raise SystemExit("FAIL CLOSED: pinned .2.9.1 runner missing normalize_rows")
    if not hasattr(helper5213, "make_hypothesis_analyze") or not hasattr(helper5213, "arm_spec"):
        raise SystemExit("FAIL CLOSED: pinned .2.13.1 runner missing causal-arm helpers")

    sessions = load_spy_sessions()
    bundle_paths = sorted((bundle_root / "monthly").glob("*.json"))
    if len(bundle_paths) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(bundle_paths)}")

    records = []
    classification_counts = Counter()
    timeframe_counts = Counter()
    side_counts = Counter()
    bundle_residual_counts = Counter()
    native_missing_total = 0
    no_top12_missing_total = 0

    for path in bundle_paths:
        bundle = load_json(path)
        rows = helper529.normalize_rows(bundle)
        frozen = bundle.get("frozen_profile")
        identity = bundle.get("prediction_identity")
        if not isinstance(frozen, dict) or not isinstance(identity, dict):
            raise SystemExit(f"FAIL CLOSED: malformed bundle authority: {path}")

        symbol = str(identity.get("symbol") or "")
        as_of_raw = identity.get("as_of")
        if not symbol or not as_of_raw:
            raise SystemExit(f"FAIL CLOSED: incomplete prediction_identity: {path}")
        as_of = dt.date.fromisoformat(str(as_of_raw)[:10])

        control_service = native.StockIntelligenceService()
        level_source = inspect.getsource(type(control_service.levels))
        if hashlib.sha256(level_source.encode()).hexdigest() != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
            raise SystemExit("FAIL CLOSED: LevelIntelligenceService source SHA drift")
        sr_source = inspect.getsource(type(control_service.levels.sr))
        if hashlib.sha256(sr_source.encode()).hexdigest() != EXPECTED_SR_SOURCE_SHA256:
            raise SystemExit("FAIL CLOSED: SupportResistanceEngine source SHA drift")

        control_profile = native.call_profile(control_service, symbol, rows, as_of, sessions, 300, 750)
        if control_profile is None:
            raise RuntimeError(f"native control profile ineligible for {symbol}")

        frozen_support = list(frozen.get("support_levels") or [])
        frozen_resistance = list(frozen.get("resistance_levels") or [])
        native_support = list(control_profile.support_levels or [])
        native_resistance = list(control_profile.resistance_levels or [])
        native_missing_total += len(missing_frozen(frozen_support, native_support))
        native_missing_total += len(missing_frozen(frozen_resistance, native_resistance))

        service = native.StockIntelligenceService()
        sr_module = importlib.import_module(type(service.levels.sr).__module__)
        hypothesis = helper5213.make_hypothesis_analyze(
            service.levels.sr.analyze, sr_module, helper5213.arm_spec("NO_TOP12_RETENTION")
        )
        capture = capture_hypothesis_inputs(service, hypothesis)
        profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
        if profile is None:
            raise RuntimeError(f"NO_TOP12_RETENTION profile ineligible for {symbol}")

        residuals = []
        for side, frozen_items, produced_items in (
            ("support", frozen_support, list(profile.support_levels or [])),
            ("resistance", frozen_resistance, list(profile.resistance_levels or [])),
        ):
            missing = missing_frozen(frozen_items, produced_items)
            no_top12_missing_total += len(missing)
            for item in missing:
                result = classify_residual(item, side, capture)
                residuals.append(result)
                classification_counts[result["classification"]] += 1
                timeframe_counts[result["frozen_timeframe"] or "UNKNOWN"] += 1
                side_counts[side] += 1

        if residuals:
            bundle_residual_counts[symbol] += len(residuals)

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "bundle": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "residual_count": len(residuals),
            "residuals": residuals,
            "captured_timeframe_input_shapes": {
                block["timeframe"]: {
                    "row_count": len(block["rows"]),
                    "start": row_date(block["rows"][0]) if block["rows"] else None,
                    "end": row_date(block["rows"][-1]) if block["rows"] else None,
                    "support_output_count": len(block["support"]),
                    "resistance_output_count": len(block["resistance"]),
                }
                for block in capture
            },
        })

    if native_missing_total != EXPECTED_NATIVE_MISSING:
        raise SystemExit(
            f"FAIL CLOSED: native missing count drift expected={EXPECTED_NATIVE_MISSING} "
            f"actual={native_missing_total}"
        )
    if no_top12_missing_total != EXPECTED_NO_TOP12_MISSING:
        raise SystemExit(
            f"FAIL CLOSED: NO_TOP12 residual count drift expected={EXPECTED_NO_TOP12_MISSING} "
            f"actual={no_top12_missing_total}"
        )

    classifications = dict(classification_counts)
    no_provenance = classifications.get("NO_CAPTURED_OHLC_PROVENANCE", 0)
    lt20 = classifications.get("FROZEN_TIMEFRAME_NATIVE_INELIGIBLE_LT20", 0)
    pre_candidate = (
        classifications.get("FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE", 0)
        + classifications.get("CROSS_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_PROVENANCE", 0)
    )

    if lt20 > 0:
        conclusion = "RESIDUAL_DIVERGENCE_INCLUDES_TIMEFRAME_HISTORY_ELIGIBILITY_SEMANTICS"
        next_step = "BUILD_M77_19_6_5_2_15_TIMEFRAME_HISTORY_ELIGIBILITY_CAUSAL_REPLAY"
    elif pre_candidate > 0:
        conclusion = "RESIDUAL_DIVERGENCE_INCLUDES_POST_CANDIDATE_CONSOLIDATION_OR_MERGE_SEMANTICS"
        next_step = "BUILD_M77_19_6_5_2_15_POST_CANDIDATE_CONSOLIDATION_SEMANTICS_CAUSAL_REPLAY"
    elif no_provenance > 0:
        conclusion = "RESIDUAL_DIVERGENCE_REQUIRES_INPUT_HISTORY_OR_PRICE_PROVENANCE_FORENSICS"
        next_step = "BUILD_M77_19_6_5_2_15_INPUT_HISTORY_PRICE_PROVENANCE_FORENSICS"
    else:
        conclusion = "RESIDUAL_DIVERGENCE_LOCALIZED_TO_NATIVE_SELECTION_SEMANTICS"
        next_step = "BUILD_M77_19_6_5_2_15_NATIVE_SELECTION_SEMANTICS_CAUSAL_REPLAY"

    report = {
        "version": VERSION,
        "authority_5213": authority5213,
        "monthly_bundle_count": len(records),
        "native_missing_beyond_0_3pct_count": native_missing_total,
        "no_top12_residual_missing_beyond_0_3pct_count": no_top12_missing_total,
        "restored_by_no_top12_count": native_missing_total - no_top12_missing_total,
        "classification_counts": classifications,
        "frozen_timeframe_distribution": dict(timeframe_counts),
        "side_distribution": dict(side_counts),
        "bundle_residual_count_distribution": dict(Counter(bundle_residual_counts.values())),
        "bundles_with_residuals": len(bundle_residual_counts),
        "records": records,
        "forensic_conclusion": conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_control_unmodified": True,
            "no_top12_arm_is_forensic_only": True,
            "no_candidate_threshold_search_or_optimization": True,
            "native_level_merge_threshold": LEVEL_MERGE_THRESHOLD,
            "native_level_merge_threshold_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "frozen_profile_scoring_authority_only": True,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_13_report": {
                "path": str(report5213_path),
                "sha256": EXPECTED_REPORT_5213_SHA256,
            },
            "m77_19_6_5_2_13_1_runner": {
                "path": str(runner5213_path),
                "sha256": EXPECTED_RUNNER_5213_SHA256,
            },
            "native_runner": {
                "path": str(native_path),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
            "support_resistance_source_sha256": EXPECTED_SR_SOURCE_SHA256,
            "level_service_source_sha256": EXPECTED_LEVEL_SERVICE_SOURCE_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.14 RESIDUAL CANDIDATE GENERATION SEMANTICS FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5213:", authority5213)
    print("monthly_bundle_count:", len(records))
    print("native_missing_beyond_0_3pct_count:", native_missing_total)
    print("no_top12_residual_missing_beyond_0_3pct_count:", no_top12_missing_total)
    print("restored_by_no_top12_count:", native_missing_total - no_top12_missing_total)
    print("classification_counts:", classifications)
    print("frozen_timeframe_distribution:", dict(timeframe_counts))
    print("side_distribution:", dict(side_counts))
    print("bundles_with_residuals:", len(bundle_residual_counts))
    print("forensic_conclusion:", conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
