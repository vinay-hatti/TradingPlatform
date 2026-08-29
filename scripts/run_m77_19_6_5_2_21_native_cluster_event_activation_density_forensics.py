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
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

VERSION = "M77.19.6.5.2.21-NATIVE-CLUSTER-EVENT-ACTIVATION-DENSITY-FORENSICS-1.0"

REPORT_5220_REL = "reports/m77_19_6_5_2_20_native_observable_trigger_collateral_impact_forensics.json"
EXPECTED_REPORT_5220_SHA256 = "1919911096baf7b9c6d352a3af15195af65272897220b3c739a7ed0e4ee6e6c0"

RUNNER_5220_REL = "scripts/run_m77_19_6_5_2_20_native_observable_trigger_collateral_impact_forensics.py"
EXPECTED_RUNNER_5220_SHA256 = "1716c3f52f4f0d1c13890adecdceb5a93cd687430c3dd61d76dafc715c65f07c"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

EXPECTED_MONTHLY_BUNDLE_COUNT = 48
EXPECTED_SYMBOL_RECORD_COUNT = 48

LEVEL_REACHABILITY_THRESHOLD = 0.003
NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35
PARITY_TOLERANCE = 1e-9

CAUSAL_TARGETS = (
    ("AES", "resistance", 25.61),
    ("ANET", "support", 22.8919),
    ("ATO", "resistance", 103.405),
)

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

def validate_5220(report: dict[str, Any]) -> dict[str, Any]:
    split = ((report.get("arm_collateral_summaries") or {})
             .get("OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE") or {})
    preserve = ((report.get("arm_collateral_summaries") or {})
                .get("OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT") or {})
    checks = {
        "symbol_record_count_48": report.get("symbol_record_count") == EXPECTED_SYMBOL_RECORD_COUNT,
        "split_degrades_48": (split.get("joint_state_distribution") or {}).get("ANY_DEGRADATION") == 48,
        "split_non_target_degrades_45": (split.get("non_target_symbols") or {}).get("any_degradation_count") == 45,
        "preserve_degrades_43": (preserve.get("joint_state_distribution") or {}).get("ANY_DEGRADATION") == 43,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "SPLIT_WIDE_COLLATERAL_DAMAGE_IS_SYSTEMIC_ACROSS_NON_TARGET_SYMBOLS",
        "semantic_not_promoted": report.get("candidate_semantic_promoted") is False,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.20 authority validation failed: {checks}")
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

def rel_distance(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))

def describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }

def causal_label(symbol: str, side: str, candidate_price: float) -> str | None:
    for s, target_side, target_price in CAUSAL_TARGETS:
        if symbol == s and side == target_side and abs(candidate_price - target_price) <= PARITY_TOLERANCE:
            return f"{s}_{target_side.upper()}"
    return None

def build_instrumented_native_analyze(sr_module, symbol: str, sink: list[dict[str, Any]]):
    PriceLevel = sr_module.PriceLevel
    _rows = sr_module._rows
    _atr = sr_module._atr

    def analyze(timeframe, data):
        rows = _rows(data)
        n = len(rows)
        if n < 20:
            return [], []

        atr = max(_atr(rows), 1e-9)
        merge_distance = atr * NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER
        candidates = []

        radius = 2
        for i in range(radius, n - radius):
            h = float(rows[i]["high"])
            l = float(rows[i]["low"])
            window = rows[i-radius:i+radius+1]
            if h >= max(float(x["high"]) for x in window):
                candidates.append(("RESISTANCE", h, i, "PIVOT_RADIUS_2"))
            if l <= min(float(x["low"]) for x in window):
                candidates.append(("SUPPORT", l, i, "PIVOT_RADIUS_2"))

        for w in (20, 50, 100):
            if n >= w:
                candidates += [
                    ("RESISTANCE", max(float(x["high"]) for x in rows[-w:]), n-1, f"ROLLING_{w}"),
                    ("SUPPORT", min(float(x["low"]) for x in rows[-w:]), n-1, f"ROLLING_{w}"),
                ]

        out = []
        seeds: dict[int, float] = {}

        for seq, (typ, price, idx, source) in enumerate(candidates):
            eligible = []
            for pos, x in enumerate(out):
                if x.level_type != typ:
                    continue
                gap_abs = abs(float(x.price) - float(price))
                if gap_abs <= merge_distance:
                    eligible.append((pos, x, gap_abs))

            side = "support" if typ == "SUPPORT" else "resistance"
            event = {
                "symbol": symbol,
                "timeframe": timeframe,
                "side": side,
                "seq": seq,
                "candidate_source": source,
                "candidate_price": float(price),
                "atr": float(atr),
                "native_merge_distance_abs": float(merge_distance),
                "eligible_cluster_count": len(eligible),
                "cluster_count_before": len(out),
                "causal_target_label": causal_label(symbol, side, float(price)),
            }

            if eligible:
                pos, found, gap_abs = eligible[0]
                centroid_before = float(found.price)
                seed = float(seeds.get(pos, centroid_before))
                candidate_gap_rel = rel_distance(centroid_before, float(price))
                touch_before = int(found.touch_count)
                centroid_after = (
                    centroid_before * touch_before + float(price)
                ) / (touch_before + 1)
                centroid_drift_from_seed_before = rel_distance(centroid_before, seed)
                centroid_drift_from_seed_after = rel_distance(centroid_after, seed)

                event.update({
                    "native_action": "MERGE_INTO_EXISTING_CLUSTER",
                    "selected_cluster_index": pos,
                    "selected_cluster_centroid_before": centroid_before,
                    "selected_cluster_seed_price": seed,
                    "selected_cluster_touch_count_before": touch_before,
                    "candidate_gap_rel_to_centroid": candidate_gap_rel,
                    "centroid_after": centroid_after,
                    "centroid_drift_from_seed_before": centroid_drift_from_seed_before,
                    "centroid_drift_from_seed_after": centroid_drift_from_seed_after,
                    "split_wide_activation": candidate_gap_rel >= LEVEL_REACHABILITY_THRESHOLD,
                    "preserve_seed_activation": (
                        centroid_drift_from_seed_before < LEVEL_REACHABILITY_THRESHOLD
                        and centroid_drift_from_seed_after >= LEVEL_REACHABILITY_THRESHOLD
                    ),
                })

                found.price = centroid_after
                found.touch_count += 1
                found.strength = min(100, found.strength + 8)
                found.confluence_score = min(100, found.confluence_score + 10)
            else:
                age = n - 1 - idx
                strength = max(25, 80 - age * .8)
                out.append(
                    PriceLevel(
                        typ,
                        round(price, 4),
                        timeframe,
                        round(strength, 2),
                        round(strength * .75, 2),
                        1,
                        min(.9, .45 + strength / 220),
                        max(.1, .55 - strength / 220),
                        {"age_bars": age},
                        [timeframe],
                    )
                )
                seeds[len(out)-1] = float(price)
                event.update({
                    "native_action": "START_NEW_CLUSTER",
                    "selected_cluster_index": len(out)-1,
                    "selected_cluster_centroid_before": None,
                    "selected_cluster_seed_price": float(price),
                    "selected_cluster_touch_count_before": 0,
                    "candidate_gap_rel_to_centroid": None,
                    "centroid_after": float(price),
                    "centroid_drift_from_seed_before": 0.0,
                    "centroid_drift_from_seed_after": 0.0,
                    "split_wide_activation": False,
                    "preserve_seed_activation": False,
                })

            sink.append(event)

        out.sort(key=lambda x: (-x.strength, x.price))
        sup = [x for x in out if x.level_type == "SUPPORT"][:12]
        res = [x for x in out if x.level_type == "RESISTANCE"][:12]
        return sup, res

    return analyze

def activation_summary(events: list[dict[str, Any]], field: str) -> dict[str, Any]:
    activated = [e for e in events if e.get(field) is True]
    merges = [e for e in events if e.get("native_action") == "MERGE_INTO_EXISTING_CLUSTER"]
    by_tf = Counter(e["timeframe"] for e in activated)
    by_side = Counter(e["side"] for e in activated)
    by_source = Counter(e["candidate_source"] for e in activated)
    by_symbol = Counter(e["symbol"] for e in activated)

    return {
        "raw_candidate_event_count": len(events),
        "native_merge_event_count": len(merges),
        "activation_count": len(activated),
        "activation_per_1000_raw_candidates": (
            1000.0 * len(activated) / len(events) if events else 0.0
        ),
        "activation_per_1000_native_merges": (
            1000.0 * len(activated) / len(merges) if merges else 0.0
        ),
        "symbols_with_activation_count": len(by_symbol),
        "timeframe_distribution": dict(by_tf),
        "side_distribution": dict(by_side),
        "candidate_source_distribution": dict(by_source),
        "top_symbol_activation_counts": by_symbol.most_common(15),
        "candidate_gap_rel_to_centroid": describe([
            float(e["candidate_gap_rel_to_centroid"])
            for e in activated
            if e.get("candidate_gap_rel_to_centroid") is not None
        ]),
        "centroid_drift_from_seed_after": describe([
            float(e["centroid_drift_from_seed_after"])
            for e in activated
            if e.get("centroid_drift_from_seed_after") is not None
        ]),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = Path(args.bundle_root)
    if not bundle_root.is_absolute():
        bundle_root = root / bundle_root
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    report5220_path = require_file(
        root, REPORT_5220_REL, EXPECTED_REPORT_5220_SHA256, "M77.19.6.5.2.20 report"
    )
    require_file(
        root, RUNNER_5220_REL, EXPECTED_RUNNER_5220_SHA256, "M77.19.6.5.2.20 runner"
    )
    helper529_path = require_file(
        root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256, "M77.19.6.5.2.9.1 runner"
    )
    native_path = require_file(
        root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256, "native replay runner"
    )

    authority = validate_5220(load_json(report5220_path))
    helper529 = import_module_from_path(helper529_path, "m77_helper_529_for_5221")
    native = import_module_from_path(native_path, "m77_native_5221")
    sessions = load_spy_sessions()

    probe = native.StockIntelligenceService()
    level_source = inspect.getsource(type(probe.levels))
    if hashlib.sha256(level_source.encode()).hexdigest() != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
        raise SystemExit("FAIL CLOSED: LevelIntelligenceService source SHA drift")
    sr_source = inspect.getsource(type(probe.levels.sr))
    if hashlib.sha256(sr_source.encode()).hexdigest() != EXPECTED_SR_SOURCE_SHA256:
        raise SystemExit("FAIL CLOSED: SupportResistanceEngine source SHA drift")
    sr_module = importlib.import_module(type(probe.levels.sr).__module__)

    bundle_paths = sorted((bundle_root / "monthly").glob("*.json"))
    if len(bundle_paths) != EXPECTED_MONTHLY_BUNDLE_COUNT:
        raise SystemExit(
            f"FAIL CLOSED: expected {EXPECTED_MONTHLY_BUNDLE_COUNT} monthly bundles, "
            f"found {len(bundle_paths)}"
        )

    events: list[dict[str, Any]] = []
    symbol_event_counts = {}

    for path in bundle_paths:
        bundle = load_json(path)
        identity = bundle.get("prediction_identity") or {}
        symbol = str(identity.get("symbol") or "")
        as_of = dt.date.fromisoformat(str(identity.get("as_of"))[:10])
        rows = helper529.normalize_rows(bundle)

        before = len(events)
        service = native.StockIntelligenceService()
        service.levels.sr.analyze = build_instrumented_native_analyze(sr_module, symbol, events)
        profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
        if profile is None:
            raise SystemExit(f"FAIL CLOSED: native profile ineligible for {symbol}")
        symbol_event_counts[symbol] = len(events) - before

    split_summary = activation_summary(events, "split_wide_activation")
    preserve_summary = activation_summary(events, "preserve_seed_activation")

    causal_events = [e for e in events if e.get("causal_target_label")]
    if len(causal_events) != 3:
        raise SystemExit(
            f"FAIL CLOSED: expected 3 exact causal candidate events, observed {len(causal_events)}"
        )

    causal_projection = []
    for e in causal_events:
        causal_projection.append({
            "label": e["causal_target_label"],
            "symbol": e["symbol"],
            "timeframe": e["timeframe"],
            "side": e["side"],
            "candidate_source": e["candidate_source"],
            "native_action": e["native_action"],
            "eligible_cluster_count": e["eligible_cluster_count"],
            "selected_cluster_touch_count_before": e["selected_cluster_touch_count_before"],
            "candidate_gap_rel_to_centroid": e["candidate_gap_rel_to_centroid"],
            "centroid_drift_from_seed_before": e["centroid_drift_from_seed_before"],
            "centroid_drift_from_seed_after": e["centroid_drift_from_seed_after"],
            "split_wide_activation": e["split_wide_activation"],
            "preserve_seed_activation": e["preserve_seed_activation"],
        })

    background_split = [
        e for e in events
        if e.get("split_wide_activation") and not e.get("causal_target_label")
    ]
    background_preserve = [
        e for e in events
        if e.get("preserve_seed_activation") and not e.get("causal_target_label")
    ]

    split_sparse = (
        split_summary["activation_per_1000_native_merges"] <= 25.0
        and split_summary["symbols_with_activation_count"] <= 10
    )
    preserve_sparse = (
        preserve_summary["activation_per_1000_native_merges"] <= 25.0
        and preserve_summary["symbols_with_activation_count"] <= 10
    )

    if split_sparse or preserve_sparse:
        conclusion = "AT_LEAST_ONE_EXISTING_OBSERVABLE_TRIGGER_IS_NATURALLY_SPARSE_ENOUGH_FOR_EVENT_STATE_DISCRIMINATION"
        next_step = "BUILD_M77_19_6_5_2_22_NATIVE_EVENT_STATE_DISCRIMINATOR_FORENSICS"
    else:
        conclusion = "EXISTING_OBSERVABLE_TRIGGERS_ACTIVATE_DENSELY_ACROSS_NATIVE_CLUSTER_EVENTS"
        next_step = "BUILD_M77_19_6_5_2_22_NATIVE_EVENT_STATE_DISCRIMINATOR_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5220": authority,
        "monthly_bundle_count": len(bundle_paths),
        "total_raw_candidate_event_count": len(events),
        "symbol_event_counts": symbol_event_counts,
        "activation_density": {
            "OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE": split_summary,
            "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT": preserve_summary,
        },
        "causal_event_projection": causal_projection,
        "background_activation_counts": {
            "split_wide_non_causal_activation_count": len(background_split),
            "preserve_seed_non_causal_activation_count": len(background_preserve),
        },
        "forensic_conclusion": conclusion,
        "candidate_semantic_promoted": False,
        "new_trigger_semantic_introduced": False,
        "new_threshold_introduced": False,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_candidate_generation_unchanged": True,
            "native_top12_retention_unchanged": True,
            "native_internal_atr_merge_multiplier": NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER,
            "native_internal_atr_merge_multiplier_relaxed": False,
            "native_level_merge_threshold": LEVEL_REACHABILITY_THRESHOLD,
            "native_level_merge_threshold_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "threshold_search_or_optimization": False,
            "symbol_identity_used_in_trigger_logic": False,
            "frozen_target_identity_used_in_trigger_logic": False,
            "causal_target_identity_used_for_diagnostic_labeling_only": True,
            "historical_answer_leakage_into_trigger_logic": False,
            "candidate_semantic_promoted": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "events": events,
        "source_authorities": {
            "m77_19_6_5_2_20_report_sha256": EXPECTED_REPORT_5220_SHA256,
            "m77_19_6_5_2_20_runner_sha256": EXPECTED_RUNNER_5220_SHA256,
            "native_runner_sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            "level_service_source_sha256": EXPECTED_LEVEL_SERVICE_SOURCE_SHA256,
            "support_resistance_source_sha256": EXPECTED_SR_SOURCE_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.21 NATIVE CLUSTER EVENT ACTIVATION DENSITY FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5220:", authority)
    print("monthly_bundle_count:", len(bundle_paths))
    print("total_raw_candidate_event_count:", len(events))
    print("SPLIT_WIDE", split_summary)
    print("PRESERVE_SEED", preserve_summary)
    print("causal_event_projection:", causal_projection)
    print("background_activation_counts:", report["background_activation_counts"])
    print("forensic_conclusion:", conclusion)
    print("candidate_semantic_promoted: False")
    print("new_trigger_semantic_introduced: False")
    print("new_threshold_introduced: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
