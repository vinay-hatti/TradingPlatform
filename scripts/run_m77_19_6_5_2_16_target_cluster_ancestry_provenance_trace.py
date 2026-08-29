#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.16-TARGET-CLUSTER-ANCESTRY-PROVENANCE-TRACE-1.0"

REPORT_5215_REL = "reports/m77_19_6_5_2_15_post_candidate_consolidation_semantics_causal_replay.json"
EXPECTED_REPORT_5215_SHA256 = "586cefbb9f01771e1e9dd3f632406a32d559092c5440e3d8ab0e9f0bb81a1768"

RUNNER_5215_REL = "scripts/run_m77_19_6_5_2_15_post_candidate_consolidation_semantics_causal_replay.py"
EXPECTED_RUNNER_5215_SHA256 = "8e4a3f5f3b723fdfa50ab5ced170f9c5e1605cd0256870b76f1d0de87851bcb0"

REPORT_5214_REL = "reports/m77_19_6_5_2_14_residual_candidate_generation_semantics_forensics.json"
EXPECTED_REPORT_5214_SHA256 = "3cced0fca689833455e548e9f5f66fe54bcad5bd9b53f470af62f7c4f7ca275b"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

PARITY_TOLERANCE = 1e-9
LEVEL_REACHABILITY_THRESHOLD = 0.003
NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35
EXPECTED_TARGET_COUNT = 3

EXPECTED_5215 = {
    "native_missing": 67,
    "no_top12_missing": 54,
    "keep_seed_missing": 472,
    "keep_seed_exact": 479,
    "keep_seed_recovered": 2,
}

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def require_file(root: Path, rel: str, sha: str, label: str) -> Path:
    p = root / rel
    if not p.exists():
        raise SystemExit(f"FAIL CLOSED: required {label} missing: {rel}")
    actual = sha256_file(p)
    if actual != sha:
        raise SystemExit(f"FAIL CLOSED: {label} SHA drift expected={sha} actual={actual}")
    return p

def import_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAIL CLOSED: unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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

def validate_5215(report: dict[str, Any]) -> dict[str, Any]:
    arms = report.get("arm_summaries") or {}
    keep = arms.get("NO_TOP12_KEEP_SEED_PRICE") or {}
    native = arms.get("NATIVE_CONTROL") or {}
    base = arms.get("NO_TOP12_BASELINE") or {}
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "native_missing_67": native.get("missing_beyond_0_3pct_count") == EXPECTED_5215["native_missing"],
        "no_top12_missing_54": base.get("missing_beyond_0_3pct_count") == EXPECTED_5215["no_top12_missing"],
        "keep_seed_missing_472": keep.get("missing_beyond_0_3pct_count") == EXPECTED_5215["keep_seed_missing"],
        "keep_seed_exact_479": keep.get("exact_frozen_match_count") == EXPECTED_5215["keep_seed_exact"],
        "keep_seed_recovered_2": keep.get("preconsolidation_target_recovered_count") == EXPECTED_5215["keep_seed_recovered"],
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: .2.15 authority validation failed: {checks}")
    return checks

def extract_targets(report5214: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for rec in report5214.get("records") or []:
        symbol = str(rec.get("symbol") or "")
        for residual in rec.get("residuals") or []:
            if residual.get("classification") != "FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE":
                continue
            frozen = residual.get("frozen_level") or {}
            out.append({
                "symbol": symbol,
                "side": str(residual.get("side") or ""),
                "timeframe": str(frozen.get("timeframe") or ""),
                "price": float(frozen.get("price")),
                "source_residual": residual,
            })
    if len(out) != EXPECTED_TARGET_COUNT:
        raise SystemExit(f"FAIL CLOSED: expected {EXPECTED_TARGET_COUNT} preconsolidation targets, found {len(out)}")
    return out

def candidate_events(sr_module, timeframe: str, data: Any) -> tuple[list[dict[str, Any]], float]:
    rows = sr_module._rows(data)
    n = len(rows)
    if n < 20:
        return [], 0.0
    atr = max(sr_module._atr(rows), 1e-9)
    merge_distance = atr * NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER
    events = []
    seq = 0

    radius = 2
    for i in range(radius, n - radius):
        h = float(rows[i]["high"])
        l = float(rows[i]["low"])
        window = rows[i-radius:i+radius+1]
        if h >= max(float(x["high"]) for x in window):
            events.append({"seq": seq, "type": "RESISTANCE", "price": h, "idx": i, "source": "PIVOT_RADIUS_2"})
            seq += 1
        if l <= min(float(x["low"]) for x in window):
            events.append({"seq": seq, "type": "SUPPORT", "price": l, "idx": i, "source": "PIVOT_RADIUS_2"})
            seq += 1

    for w in (20, 50, 100):
        if n >= w:
            events.append({"seq": seq, "type": "RESISTANCE",
                            "price": max(float(x["high"]) for x in rows[-w:]),
                            "idx": n-1, "source": f"ROLLING_{w}_HIGH"})
            seq += 1
            events.append({"seq": seq, "type": "SUPPORT",
                            "price": min(float(x["low"]) for x in rows[-w:]),
                            "idx": n-1, "source": f"ROLLING_{w}_LOW"})
            seq += 1
    return events, merge_distance

def trace_consolidation(events: list[dict[str, Any]], merge_distance: float,
                        target_price: float, target_side: str) -> dict[str, Any]:
    target_type = "SUPPORT" if target_side.lower() == "support" else "RESISTANCE"
    clusters: list[dict[str, Any]] = []
    event_trace = []
    target_event_ids = []

    for e in events:
        eligible = []
        for ci, c in enumerate(clusters):
            if c["type"] != e["type"]:
                continue
            d = abs(float(c["centroid"]) - float(e["price"]))
            if d <= merge_distance:
                eligible.append((ci, d))

        before = None
        after = None
        action = None
        cluster_id = None

        if eligible:
            ci, distance = eligible[0]
            c = clusters[ci]
            before = float(c["centroid"])
            c["centroid"] = (
                c["centroid"] * c["touch_count"] + float(e["price"])
            ) / (c["touch_count"] + 1)
            c["touch_count"] += 1
            c["members"].append(dict(e))
            after = float(c["centroid"])
            cluster_id = ci
            action = "MERGED_INTO_FIRST_ELIGIBLE_CLUSTER"
        else:
            cluster_id = len(clusters)
            clusters.append({
                "id": cluster_id,
                "type": e["type"],
                "seed_price": float(e["price"]),
                "centroid": float(e["price"]),
                "touch_count": 1,
                "members": [dict(e)],
            })
            before = None
            after = float(e["price"])
            action = "SEEDED_NEW_CLUSTER"

        if e["type"] == target_type and abs(float(e["price"]) - target_price) <= PARITY_TOLERANCE:
            target_event_ids.append(e["seq"])

        event_trace.append({
            **e,
            "cluster_id": cluster_id,
            "action": action,
            "centroid_before": before,
            "centroid_after": after,
            "eligible_cluster_count": len(eligible),
            "eligible_cluster_distances": [
                {"cluster_id": ci, "distance": d} for ci, d in eligible
            ],
            "is_exact_target_candidate": (
                e["type"] == target_type and
                abs(float(e["price"]) - target_price) <= PARITY_TOLERANCE
            ),
        })

    target_cluster_ids = sorted({
        x["cluster_id"] for x in event_trace if x["is_exact_target_candidate"]
    })
    cluster_details = [clusters[i] for i in target_cluster_ids]

    reachable_final = any(
        abs(float(c["centroid"]) - target_price) / max(1.0, abs(target_price))
        < LEVEL_REACHABILITY_THRESHOLD
        for c in clusters if c["type"] == target_type
    )

    causal_class = "UNKNOWN"
    if target_event_ids:
        first_target = next(x for x in event_trace if x["seq"] == target_event_ids[0])
        if first_target["action"] == "SEEDED_NEW_CLUSTER":
            target_cluster = clusters[first_target["cluster_id"]]
            if not reachable_final and abs(target_cluster["centroid"] - target_price) > PARITY_TOLERANCE:
                causal_class = "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"
            else:
                causal_class = "TARGET_SEEDS_CLUSTER_OTHER"
        else:
            causal_class = "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER"

    return {
        "target_event_ids": target_event_ids,
        "target_cluster_ids": target_cluster_ids,
        "target_cluster_details": cluster_details,
        "target_reachable_after_native_consolidation": reachable_final,
        "causal_classification": causal_class,
        "event_trace": event_trace,
        "final_clusters": clusters,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = (root / args.bundle_root).resolve() if not Path(args.bundle_root).is_absolute() else Path(args.bundle_root)
    output = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    report5215_path = require_file(root, REPORT_5215_REL, EXPECTED_REPORT_5215_SHA256, "M77.19.6.5.2.15 report")
    require_file(root, RUNNER_5215_REL, EXPECTED_RUNNER_5215_SHA256, "M77.19.6.5.2.15 runner")
    report5214_path = require_file(root, REPORT_5214_REL, EXPECTED_REPORT_5214_SHA256, "M77.19.6.5.2.14 report")
    runner529_path = require_file(root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256, "M77.19.6.5.2.9.1 runner")
    native_path = require_file(root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256, "native replay runner")

    report5215 = load_json(report5215_path)
    authority5215 = validate_5215(report5215)
    report5214 = load_json(report5214_path)
    targets = extract_targets(report5214)

    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5216")
    native = import_module_from_path(native_path, "m77_native_5216")
    sessions = load_spy_sessions()

    probe = native.StockIntelligenceService()
    level_source = inspect.getsource(type(probe.levels))
    if hashlib.sha256(level_source.encode()).hexdigest() != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
        raise SystemExit("FAIL CLOSED: LevelIntelligenceService source SHA drift")
    sr_source = inspect.getsource(type(probe.levels.sr))
    if hashlib.sha256(sr_source.encode()).hexdigest() != EXPECTED_SR_SOURCE_SHA256:
        raise SystemExit("FAIL CLOSED: SupportResistanceEngine source SHA drift")
    sr_module = importlib.import_module(type(probe.levels.sr).__module__)

    monthly = sorted((bundle_root / "monthly").glob("*.json"))
    by_symbol = {}
    for p in monthly:
        b = load_json(p)
        identity = b.get("prediction_identity") or {}
        by_symbol[str(identity.get("symbol") or "")] = (p, b)

    records = []
    counts: dict[str, int] = {}

    for target in targets:
        symbol = target["symbol"]
        if symbol not in by_symbol:
            raise SystemExit(f"FAIL CLOSED: bundle missing for target symbol {symbol}")
        path, bundle = by_symbol[symbol]
        rows = helper529.normalize_rows(bundle)
        as_of = dt.date.fromisoformat(str((bundle.get("prediction_identity") or {}).get("as_of"))[:10])

        # Native profile remains an unmodified control and proves the target is still missing.
        service = native.StockIntelligenceService()
        profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
        if profile is None:
            raise SystemExit(f"FAIL CLOSED: native profile ineligible for {symbol}")
        produced = (
            list(profile.support_levels or [])
            if target["side"].lower() == "support"
            else list(profile.resistance_levels or [])
        )
        native_reachable = any(
            abs(float(getattr(x, "price", x.get("price") if isinstance(x, dict) else 0.0)) - target["price"])
            / max(1.0, abs(target["price"])) < LEVEL_REACHABILITY_THRESHOLD
            for x in produced
        )
        if native_reachable:
            raise SystemExit(f"FAIL CLOSED: target unexpectedly reachable in native control {symbol} {target['price']}")

        timeframe_data = None
        frozen_tf = target["timeframe"]
        # The exact frozen bundle already carries the captured native timeframe inputs used by prior phases.
        for key in (
            "captured_native_timeframe_inputs",
            "native_timeframe_inputs",
            "timeframe_inputs",
        ):
            node = bundle.get(key)
            if isinstance(node, dict) and frozen_tf in node:
                timeframe_data = node[frozen_tf]
                break

        if timeframe_data is None:
            # Reuse the pinned helper's extraction semantics when bundle layout is nested differently.
            if hasattr(helper529, "captured_timeframe_rows"):
                timeframe_data = helper529.captured_timeframe_rows(bundle, frozen_tf)
            elif hasattr(helper529, "extract_timeframe_rows"):
                timeframe_data = helper529.extract_timeframe_rows(bundle, frozen_tf)

        if timeframe_data is None:
            # Final fail-closed fallback: use the exact normalized rows only for 1d; never synthesize 1w.
            if frozen_tf == "1d":
                timeframe_data = rows
            else:
                raise SystemExit(f"FAIL CLOSED: exact captured timeframe input unavailable for {symbol} {frozen_tf}")

        events, merge_distance = candidate_events(sr_module, frozen_tf, timeframe_data)
        trace = trace_consolidation(events, merge_distance, target["price"], target["side"])
        if not trace["target_event_ids"]:
            raise SystemExit(f"FAIL CLOSED: exact target candidate not found during traced candidate generation {symbol} {target['price']}")

        c = trace["causal_classification"]
        counts[c] = counts.get(c, 0) + 1

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "bundle": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "target": target,
            "merge_distance": merge_distance,
            "native_target_reachable": native_reachable,
            "trace": trace,
        })

    if sum(counts.values()) != EXPECTED_TARGET_COUNT:
        raise SystemExit("FAIL CLOSED: target causal classification count drift")

    # This phase is diagnostic only. It deliberately does not select or replay a production candidate semantic.
    if counts.get("TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS", 0) >= 1 and counts.get("TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER", 0) >= 1:
        conclusion = "PRECONSOLIDATION_RESIDUALS_SPLIT_BETWEEN_CENTROID_DRIFT_AND_PREEXISTING_CLUSTER_ABSORPTION"
    elif counts.get("TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS", 0) == EXPECTED_TARGET_COUNT:
        conclusion = "ALL_PRECONSOLIDATION_RESIDUALS_CAUSED_BY_POST_SEED_CENTROID_DRIFT"
    elif counts.get("TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER", 0) == EXPECTED_TARGET_COUNT:
        conclusion = "ALL_PRECONSOLIDATION_RESIDUALS_CAUSED_BY_PREEXISTING_CLUSTER_ABSORPTION"
    else:
        conclusion = "PRECONSOLIDATION_RESIDUALS_REQUIRE_ADDITIONAL_CLUSTER_ANCESTRY_FORENSICS"

    next_step = "BUILD_M77_19_6_5_2_17_MINIMAL_CLUSTER_ANCESTRY_CAUSAL_REPLAY"

    report = {
        "version": VERSION,
        "authority_5215": authority5215,
        "target_count": len(records),
        "classification_counts": counts,
        "forensic_conclusion": conclusion,
        "records": records,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "candidate_semantic_promoted": False,
        "keep_seed_price_globally_rejected": True,
        "keep_seed_price_rejection_reason": {
            "baseline_missing": 54,
            "keep_seed_missing": 472,
            "baseline_exact": 1329,
            "keep_seed_exact": 479,
        },
        "next_step": next_step,
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_control_unmodified": True,
            "candidate_generation_frozen": {
                "pivot_radius": 2,
                "rolling_windows": [20, 50, 100],
            },
            "native_internal_atr_merge_multiplier": NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER,
            "native_internal_atr_merge_multiplier_relaxed": False,
            "native_level_merge_threshold": LEVEL_REACHABILITY_THRESHOLD,
            "native_level_merge_threshold_relaxed": False,
            "threshold_search_or_optimization": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_15_report_sha256": EXPECTED_REPORT_5215_SHA256,
            "m77_19_6_5_2_15_runner_sha256": EXPECTED_RUNNER_5215_SHA256,
            "m77_19_6_5_2_14_report_sha256": EXPECTED_REPORT_5214_SHA256,
            "native_runner_sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            "level_service_source_sha256": EXPECTED_LEVEL_SERVICE_SOURCE_SHA256,
            "support_resistance_source_sha256": EXPECTED_SR_SOURCE_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.16 TARGET CLUSTER ANCESTRY PROVENANCE TRACE ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5215:", authority5215)
    print("target_count:", len(records))
    print("classification_counts:", counts)
    for r in records:
        print("target:", r["symbol"], r["target"]["side"], r["target"]["timeframe"], r["target"]["price"],
              "=>", r["trace"]["causal_classification"])
    print("forensic_conclusion:", conclusion)
    print("keep_seed_price_globally_rejected: True")
    print("candidate_semantic_promoted: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
