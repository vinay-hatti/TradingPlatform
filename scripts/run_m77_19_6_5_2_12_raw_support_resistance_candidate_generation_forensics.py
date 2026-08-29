#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.12-RAW-SUPPORT-RESISTANCE-CANDIDATE-GENERATION-FORENSICS-1.0"

REPORT_5211_REL = "reports/m77_19_6_5_2_11_level_selection_hypothesis_causal_replay.json"
EXPECTED_REPORT_5211_SHA256 = "88e9e9b4781727b59254c9ae6a583cea27dece55bc034bc0064c686638c101d6"

RUNNER_5211_REL = "scripts/run_m77_19_6_5_2_11_level_selection_hypothesis_causal_replay.py"
# This is the installed .2.11.1 repaired runner.
EXPECTED_RUNNER_5211_SHA256 = "1c93e515a111eb9f28c448775addaace1e727262e9ce0885528dcbb6fb4a76b4"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"

PARITY_TOLERANCE = 1e-9
MERGE_THRESHOLD = 0.003

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
        raise SystemExit(
            f"FAIL CLOSED: {label} SHA drift: expected={expected_sha} actual={actual}"
        )
    return path

def import_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAIL CLOSED: unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def validate_5211(report: dict[str, Any]) -> dict[str, Any]:
    native = (report.get("arm_summaries") or {}).get("NATIVE_FIRST_ASCENDING") or {}
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "native_is_winner": (report.get("ranking") or [None])[0] == "NATIVE_FIRST_ASCENDING",
        "forensic_conclusion": report.get("forensic_conclusion")
            == "NO_ALTERNATIVE_CLUSTER_REPRESENTATIVE_RULE_OUTPERFORMS_NATIVE",
        "native_support_not_exact": ((native.get("support") or {}).get("exact_price_set_bundle_count", 48) < 48),
        "native_resistance_not_exact": ((native.get("resistance") or {}).get("exact_price_set_bundle_count", 48) < 48),
        "merge_threshold_fixed": (report.get("governance") or {}).get("merge_threshold") == 0.003,
        "threshold_not_relaxed": (report.get("governance") or {}).get("merge_threshold_relaxed") is False,
        "candidate_generation_unmodified": (report.get("governance") or {}).get(
            "native_support_resistance_candidate_generation_unmodified"
        ) is True,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.11 authority validation failed: {checks}")
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
    out = set()
    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        out.add(value)
    if not out:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")
    return out

def level_price(x: Any) -> float:
    value = x.get("price") if isinstance(x, dict) else getattr(x, "price", None)
    if value is None:
        raise ValueError("level missing price")
    return float(value)

def numeric_attr(x: Any, field: str, default: float = 0.0) -> float:
    value = x.get(field, default) if isinstance(x, dict) else getattr(x, field, default)
    try:
        return float(value)
    except Exception:
        return float(default)

def exact(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE

def rel_distance(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))

def normalize_date(value: Any) -> str:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()[:10]
    return str(value)[:10]

def row_date(row: Any) -> str:
    if isinstance(row, dict):
        for k in ("date","timestamp","datetime","time"):
            if k in row:
                return normalize_date(row[k])
    for k in ("date","timestamp","datetime","time"):
        if hasattr(row, k):
            return normalize_date(getattr(row,k))
    return ""

def row_num(row: Any, key: str):
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    try:
        return float(value)
    except Exception:
        return None

def cluster_native_membership(levels: list[Any]) -> list[list[Any]]:
    ordered = sorted(levels, key=level_price)
    clusters: list[list[Any]] = []
    anchors: list[float] = []
    for item in ordered:
        price = level_price(item)
        chosen = None
        for idx, anchor in enumerate(anchors):
            if abs(anchor-price)/max(1.0, price) < MERGE_THRESHOLD:
                chosen = idx
                break
        if chosen is None:
            clusters.append([item])
            anchors.append(price)
        else:
            clusters[chosen].append(item)
    return clusters

def capture_raw_sr_candidates(service: Any):
    original = service.levels.sr.analyze
    capture = []
    def wrapped(timeframe, data):
        support, resistance = original(timeframe, data)
        input_rows = copy.deepcopy(list(data or []))
        capture.append({
            "timeframe": str(timeframe),
            "input_row_count": len(input_rows),
            "input_start": row_date(input_rows[0]) if input_rows else None,
            "input_end": row_date(input_rows[-1]) if input_rows else None,
            "input_rows": input_rows,
            "support": copy.deepcopy(list(support or [])),
            "resistance": copy.deepcopy(list(resistance or [])),
        })
        return support, resistance
    service.levels.sr.analyze = wrapped
    def restore():
        service.levels.sr.analyze = original
    return capture, restore

def source_semantics(obj: Any) -> dict[str, Any]:
    source = inspect.getsource(obj)
    tree = ast.parse(source)
    numeric = []
    calls = Counter()
    comparisons = []
    slices = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int,float)):
            numeric.append(node.value)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls[node.func.id] += 1
            elif isinstance(node.func, ast.Attribute):
                calls[node.func.attr] += 1
        elif isinstance(node, ast.Compare):
            comparisons.append(ast.unparse(node))
        elif isinstance(node, ast.Subscript):
            s = ast.unparse(node)
            if ":" in s:
                slices.append(s)
    return {
        "type": f"{obj.__module__}.{obj.__qualname__}",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_line_count": len(source.splitlines()),
        "numeric_literals": numeric,
        "call_names": dict(calls),
        "comparisons": comparisons,
        "slice_expressions": slices,
        "source": source,
    }

def flatten(capture: list[dict[str,Any]], side: str) -> list[dict[str,Any]]:
    out = []
    for block in capture:
        tf = block["timeframe"]
        for item in block[side]:
            out.append({
                "timeframe": tf,
                "price": level_price(item),
                "strength": numeric_attr(item,"strength"),
                "confluence_score": numeric_attr(item,"confluence_score"),
                "touch_count": numeric_attr(item,"touch_count"),
            })
    return out

def nearest(price: float, candidates: list[dict[str,Any]]):
    if not candidates:
        return None
    hit = min(candidates, key=lambda x: abs(x["price"]-price))
    return {
        **hit,
        "abs_error": abs(hit["price"]-price),
        "rel_error": rel_distance(hit["price"], price),
        "exact": exact(hit["price"],price),
        "within_merge_threshold": rel_distance(hit["price"],price) < MERGE_THRESHOLD,
    }

def row_provenance(candidate_price: float, rows_by_tf: dict[str,list[Any]], tf: str) -> dict[str,Any]:
    rows = rows_by_tf.get(tf) or []
    best = None
    for r in rows:
        for field in ("open","high","low","close"):
            v = row_num(r, field)
            if v is None:
                continue
            err = abs(v-candidate_price)
            rec = {
                "field": field,
                "date": row_date(r),
                "value": v,
                "abs_error": err,
                "rel_error": rel_distance(v,candidate_price),
                "exact": exact(v,candidate_price),
            }
            if best is None or rec["abs_error"] < best["abs_error"]:
                best = rec
    return best or {}

def classify_frozen(frozen_items, raw, anchors):
    counts = Counter()
    records = []
    for item in frozen_items:
        fp = level_price(item)
        nr = nearest(fp, raw)
        na = nearest(fp, anchors)
        if na and na["exact"]:
            cls = "EXACT_NATIVE_CLUSTER_ANCHOR"
        elif nr and nr["exact"]:
            cls = "EXACT_RAW_CANDIDATE_BUT_NOT_NATIVE_CLUSTER_ANCHOR"
        elif nr and nr["within_merge_threshold"]:
            cls = "RAW_CANDIDATE_WITHIN_0_3PCT_BUT_PRICE_DIFFERS"
        else:
            cls = "NO_NATIVE_RAW_CANDIDATE_WITHIN_0_3PCT"
        counts[cls] += 1
        records.append({
            "frozen_price": fp,
            "classification": cls,
            "nearest_raw": nr,
            "nearest_cluster_anchor": na,
        })
    return dict(counts), records

def summarize_classifications(records, side):
    counts = Counter()
    total = 0
    no_near = 0
    by_tf = Counter()
    for rec in records:
        for item in rec[side]["frozen_classification_records"]:
            total += 1
            counts[item["classification"]] += 1
            nr = item.get("nearest_raw") or {}
            if item["classification"] == "NO_NATIVE_RAW_CANDIDATE_WITHIN_0_3PCT":
                no_near += 1
            if nr.get("timeframe"):
                by_tf[nr["timeframe"]] += 1
    return {
        "frozen_level_total": total,
        "classification_counts": dict(counts),
        "no_raw_candidate_within_0_3pct_count": no_near,
        "nearest_raw_timeframe_distribution": dict(by_tf),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = (root/args.bundle_root).resolve() if not Path(args.bundle_root).is_absolute() else Path(args.bundle_root)
    output = (root/args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    report5211_path = require_file(root, REPORT_5211_REL, EXPECTED_REPORT_5211_SHA256, "M77.19.6.5.2.11 report")
    runner5211_path = require_file(root, RUNNER_5211_REL, EXPECTED_RUNNER_5211_SHA256, "M77.19.6.5.2.11.1 runner")
    runner529_path = require_file(root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256, "M77.19.6.5.2.9.1 repaired runner")
    native_path = require_file(root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256, "native replay runner")

    report5211 = load_json(report5211_path)
    authority5211 = validate_5211(report5211)

    helper5211 = import_module_from_path(runner5211_path, "m77_helper_5211_for_5212")
    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5212")
    native = import_module_from_path(native_path, "m77_native_5212")
    if not hasattr(helper529, "normalize_rows"):
        raise SystemExit("FAIL CLOSED: pinned .2.9 runner missing normalize_rows")
    # M77.19.6.5.2.12.1 authority repair:
    # helper529 is authoritative only for normalize_rows. Bundle identity is
# authoritative from prediction_identity, and frozen replay authority
    # is the bundle's canonical frozen_profile, matching the pinned .2.11.1 runner.

    sessions = load_spy_sessions()
    bundle_paths = sorted((bundle_root/"monthly").glob("*.json"))
    if len(bundle_paths) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(bundle_paths)}")

    records = []
    sr_semantics = None

    for path in bundle_paths:
        bundle = load_json(path)
        rows = helper529.normalize_rows(bundle)
        frozen_output = bundle.get("frozen_profile")
        if not isinstance(frozen_output, dict):
            raise SystemExit(
                f"FAIL CLOSED: bundle missing canonical frozen_profile authority: {path}"
            )
        identity = bundle.get("prediction_identity")
        if not isinstance(identity, dict):
            raise SystemExit(
                f"FAIL CLOSED: bundle missing prediction_identity authority: {path}"
            )

        symbol = identity.get("symbol")
        as_of_raw = identity.get("as_of")

        if not symbol:
            raise SystemExit(
                f"FAIL CLOSED: prediction_identity missing symbol: {path}"
            )
        if not as_of_raw:
            raise SystemExit(
                f"FAIL CLOSED: prediction_identity missing as_of: {path}"
            )

        symbol = str(symbol)
        as_of = dt.date.fromisoformat(str(as_of_raw)[:10])

        service = native.StockIntelligenceService()
        level_source = inspect.getsource(type(service.levels))
        level_sha = hashlib.sha256(level_source.encode()).hexdigest()
        if level_sha != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
            raise SystemExit(
                f"FAIL CLOSED: LevelIntelligenceService SHA drift: expected={EXPECTED_LEVEL_SERVICE_SOURCE_SHA256} actual={level_sha}"
            )

        if sr_semantics is None:
            sr_semantics = source_semantics(type(service.levels.sr))

        capture, restore = capture_raw_sr_candidates(service)
        try:
            profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
        finally:
            restore()
        if profile is None:
            raise RuntimeError(f"native profile ineligible for {symbol}")

        rows_by_tf = {
            block["timeframe"]: block["input_rows"]
            for block in capture
        }
        if not rows_by_tf:
            raise SystemExit(
                f"FAIL CLOSED: no captured SupportResistanceEngine timeframe inputs: {path}"
            )

        side_result = {}
        for side, frozen_key in (("support","support_levels"),("resistance","resistance_levels")):
            raw = flatten(capture, side)
            clusters = cluster_native_membership([
                type("L",(object,),x)() for x in raw
            ])
            anchors = []
            for c in clusters:
                x = sorted(c, key=level_price)[0]
                anchors.append({
                    "timeframe": getattr(x,"timeframe",""),
                    "price": level_price(x),
                    "strength": numeric_attr(x,"strength"),
                    "confluence_score": numeric_attr(x,"confluence_score"),
                    "touch_count": numeric_attr(x,"touch_count"),
                })
            frozen_items = (frozen_output or {}).get(frozen_key) or []
            class_counts, class_records = classify_frozen(frozen_items, raw, anchors)

            for item in raw:
                item["nearest_ohlc_provenance"] = row_provenance(
                    item["price"], rows_by_tf, item["timeframe"]
                )

            side_result[side] = {
                "raw_candidate_count": len(raw),
                "native_cluster_anchor_count": len(anchors),
                "frozen_level_count": len(frozen_items),
                "raw_candidates": raw,
                "native_cluster_anchors": anchors,
                "frozen_classification_counts": class_counts,
                "frozen_classification_records": class_records,
            }

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "bundle": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            **side_result,
        })

    support_summary = summarize_classifications(records,"support")
    resistance_summary = summarize_classifications(records,"resistance")

    def unresolved(summary):
        c = summary["classification_counts"]
        return (
            c.get("RAW_CANDIDATE_WITHIN_0_3PCT_BUT_PRICE_DIFFERS",0)
            + c.get("NO_NATIVE_RAW_CANDIDATE_WITHIN_0_3PCT",0)
            + c.get("EXACT_RAW_CANDIDATE_BUT_NOT_NATIVE_CLUSTER_ANCHOR",0)
        )

    combined_unresolved = unresolved(support_summary) + unresolved(resistance_summary)
    no_near = (
        support_summary["no_raw_candidate_within_0_3pct_count"]
        + resistance_summary["no_raw_candidate_within_0_3pct_count"]
    )

    if no_near > 0:
        conclusion = "RAW_CANDIDATE_GENERATION_HAS_MISSING_OR_NONREACHABLE_FROZEN_LEVELS"
        next_step = "BUILD_M77_19_6_5_2_13_SUPPORT_RESISTANCE_CANDIDATE_ALGORITHM_CAUSAL_HYPOTHESIS_REPLAY"
    elif combined_unresolved > 0:
        conclusion = "RAW_CANDIDATE_PRICES_DIVERGE_WHILE_CLUSTER_REACHABILITY_IS_PRESERVED"
        next_step = "BUILD_M77_19_6_5_2_13_SUPPORT_RESISTANCE_CANDIDATE_PRICE_SEMANTICS_CAUSAL_REPLAY"
    else:
        conclusion = "RAW_CANDIDATE_GENERATION_NOT_CAUSAL_REOPEN_MERGE_METADATA_BRANCH"
        next_step = "BUILD_M77_19_6_5_2_13_MERGE_METADATA_AND_CARDINALITY_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5211": authority5211,
        "monthly_bundle_count": len(records),
        "native_support_resistance_source_semantics": sr_semantics,
        "support_summary": support_summary,
        "resistance_summary": resistance_summary,
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
            "native_support_resistance_candidate_generation_unmodified": True,
            "ohlc_provenance_uses_captured_native_sr_inputs": True,
            "synthetic_candidate_replacement_used": False,
            "merge_threshold": MERGE_THRESHOLD,
            "merge_threshold_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_11_report": {
                "path": str(report5211_path),
                "sha256": EXPECTED_REPORT_5211_SHA256,
            },
            "m77_19_6_5_2_11_1_runner": {
                "path": str(runner5211_path),
                "sha256": EXPECTED_RUNNER_5211_SHA256,
            },
            "m77_19_6_5_2_9_repaired_runner": {
                "path": str(runner529_path),
                "sha256": EXPECTED_RUNNER_529_SHA256,
                "bundle_normalizer": "normalize_rows",
            },
            "native_runner": {
                "path": str(native_path),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
            "level_service_source_sha256": EXPECTED_LEVEL_SERVICE_SOURCE_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.12 RAW SUPPORT / RESISTANCE CANDIDATE GENERATION FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5211:", authority5211)
    print("monthly_bundle_count:", len(records))
    print("support_summary:", support_summary)
    print("resistance_summary:", resistance_summary)
    print("support_resistance_source_sha256:", sr_semantics["source_sha256"])
    print("forensic_conclusion:", conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
