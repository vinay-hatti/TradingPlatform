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
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.15-POST-CANDIDATE-CONSOLIDATION-SEMANTICS-CAUSAL-REPLAY-1.0"

REPORT_5214_REL = "reports/m77_19_6_5_2_14_residual_candidate_generation_semantics_forensics.json"
EXPECTED_REPORT_5214_SHA256 = "3cced0fca689833455e548e9f5f66fe54bcad5bd9b53f470af62f7c4f7ca275b"

RUNNER_5214_REL = "scripts/run_m77_19_6_5_2_14_residual_candidate_generation_semantics_forensics.py"
EXPECTED_RUNNER_5214_SHA256 = "2fc32620d3e05927f7a85ada94c4364b47b49df32c63acbe432e8556e40132dd"

RUNNER_5213_REL = "scripts/run_m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.py"
EXPECTED_RUNNER_5213_SHA256 = "c3b5b27c4327f73e6767b1381ecca758eb8b1816e4f15bf57dbd9c9bade68892"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

PARITY_TOLERANCE = 1e-9
LEVEL_REACHABILITY_THRESHOLD = 0.003
NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35

EXPECTED_NATIVE_MISSING = 67
EXPECTED_NO_TOP12_RESIDUAL = 54
EXPECTED_PRECONSOLIDATION_TARGETS = 3
EXPECTED_EXACT_OHLC_SELECTION_TARGETS = 8
EXPECTED_NEAR_OHLC_TARGETS = 41
EXPECTED_NO_OHLC_TARGETS = 2

ARMS = (
    "NATIVE_CONTROL",
    "NO_TOP12_BASELINE",
    "NO_TOP12_KEEP_SEED_PRICE",
    "NO_TOP12_NEAREST_MATCH",
    "NO_TOP12_FIXED_SEED_MEMBERSHIP",
)

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def require_file(root: Path, rel: str, expected_sha: str, label: str) -> Path:
    p = root / rel
    if not p.exists():
        raise SystemExit(f"FAIL CLOSED: required {label} missing: {rel}")
    actual = sha256_file(p)
    if actual != expected_sha:
        raise SystemExit(
            f"FAIL CLOSED: {label} SHA drift expected={expected_sha} actual={actual}"
        )
    return p

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
    v = x.get("price") if isinstance(x, dict) else getattr(x, "price", None)
    if v is None:
        raise ValueError("level missing price")
    return float(v)

def validate_5214(report: dict[str, Any]) -> dict[str, Any]:
    cls = report.get("classification_counts") or {}
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "native_missing_67": report.get("native_missing_beyond_0_3pct_count") == EXPECTED_NATIVE_MISSING,
        "no_top12_residual_54": report.get("no_top12_residual_missing_beyond_0_3pct_count") == EXPECTED_NO_TOP12_RESIDUAL,
        "preconsolidation_targets_3": cls.get("FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE") == EXPECTED_PRECONSOLIDATION_TARGETS,
        "exact_ohlc_selection_targets_8": cls.get("FROZEN_TIMEFRAME_OHLC_EXACT_BUT_NATIVE_SELECTION_EXCLUDES") == EXPECTED_EXACT_OHLC_SELECTION_TARGETS,
        "near_ohlc_targets_41": cls.get("NEAR_CAPTURED_OHLC_WITHOUT_EXACT_PROVENANCE") == EXPECTED_NEAR_OHLC_TARGETS,
        "no_ohlc_targets_2": cls.get("NO_CAPTURED_OHLC_PROVENANCE") == EXPECTED_NO_OHLC_TARGETS,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "RESIDUAL_DIVERGENCE_INCLUDES_POST_CANDIDATE_CONSOLIDATION_OR_MERGE_SEMANTICS",
        "next_step": report.get("next_step")
            == "BUILD_M77_19_6_5_2_15_POST_CANDIDATE_CONSOLIDATION_SEMANTICS_CAUSAL_REPLAY",
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.14 authority validation failed: {checks}")
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

def build_arm_analyze(sr_module, arm: str):
    PriceLevel = sr_module.PriceLevel
    _rows = sr_module._rows
    _atr = sr_module._atr

    if arm == "NATIVE_CONTROL":
        return None

    if arm not in ARMS:
        raise ValueError(arm)

    def analyze(timeframe, data):
        rows = _rows(data)
        n = len(rows)
        if n < 20:
            return [], []

        atr = max(_atr(rows), 1e-9)
        merge_distance = atr * NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER
        candidates = []

        # Native candidate generation is frozen: radius 2 + rolling 20/50/100.
        radius = 2
        for i in range(radius, n - radius):
            h = float(rows[i]["high"])
            l = float(rows[i]["low"])
            window = rows[i-radius:i+radius+1]
            if h >= max(float(x["high"]) for x in window):
                candidates.append(("RESISTANCE", h, i))
            if l <= min(float(x["low"]) for x in window):
                candidates.append(("SUPPORT", l, i))

        for w in (20, 50, 100):
            if n >= w:
                candidates += [
                    ("RESISTANCE", max(float(x["high"]) for x in rows[-w:]), n-1),
                    ("SUPPORT", min(float(x["low"]) for x in rows[-w:]), n-1),
                ]

        out = []
        seed_prices: dict[int, float] = {}

        for typ, price, idx in candidates:
            eligible = []
            for pos, x in enumerate(out):
                if x.level_type != typ:
                    continue
                comparison_price = (
                    seed_prices[pos]
                    if arm == "NO_TOP12_FIXED_SEED_MEMBERSHIP"
                    else float(x.price)
                )
                if abs(comparison_price - price) <= merge_distance:
                    eligible.append((pos, x, abs(comparison_price - price)))

            found = None
            found_pos = None
            if eligible:
                if arm == "NO_TOP12_NEAREST_MATCH":
                    found_pos, found, _ = min(eligible, key=lambda t: (t[2], t[0]))
                else:
                    found_pos, found, _ = eligible[0]

            if found is not None:
                if arm != "NO_TOP12_KEEP_SEED_PRICE":
                    found.price = (
                        found.price * found.touch_count + price
                    ) / (found.touch_count + 1)
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
                seed_prices[len(out)-1] = float(price)

        # NO_TOP12 baseline is intentional across every causal arm.
        out.sort(key=lambda x: (-x.strength, x.price))
        return (
            [x for x in out if x.level_type == "SUPPORT"],
            [x for x in out if x.level_type == "RESISTANCE"],
        )

    return analyze

def frozen_missing(frozen_items: list[Any], produced_items: list[Any]) -> list[Any]:
    produced = [level_price(x) for x in produced_items]
    return [
        x for x in frozen_items
        if not any(rel_distance(p, level_price(x)) < LEVEL_REACHABILITY_THRESHOLD for p in produced)
    ]

def exact_count(frozen_items: list[Any], produced_items: list[Any]) -> int:
    produced = [level_price(x) for x in produced_items]
    return sum(
        1 for x in frozen_items
        if any(exact(level_price(x), p) for p in produced)
    )

def target_key(symbol: str, side: str, frozen: dict[str, Any]) -> tuple[str, str, str, float]:
    return (
        symbol,
        side,
        str(frozen.get("timeframe") or ""),
        float(frozen.get("price")),
    )

def collect_targets(report: dict[str, Any]) -> dict[str, dict[tuple[str, str, str, float], dict[str, Any]]]:
    groups = {
        "PRECONSOLIDATION": {},
        "EXACT_OHLC_SELECTION": {},
        "NEAR_OHLC": {},
        "NO_OHLC": {},
    }
    mapping = {
        "FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE": "PRECONSOLIDATION",
        "FROZEN_TIMEFRAME_OHLC_EXACT_BUT_NATIVE_SELECTION_EXCLUDES": "EXACT_OHLC_SELECTION",
        "NEAR_CAPTURED_OHLC_WITHOUT_EXACT_PROVENANCE": "NEAR_OHLC",
        "NO_CAPTURED_OHLC_PROVENANCE": "NO_OHLC",
    }
    for rec in report.get("records") or []:
        symbol = str(rec.get("symbol") or "")
        for item in rec.get("residuals") or []:
            group = mapping.get(item.get("classification"))
            if not group:
                continue
            frozen = item.get("frozen_level") or {}
            key = target_key(symbol, str(item.get("side") or ""), frozen)
            groups[group][key] = {
                "symbol": symbol,
                "side": str(item.get("side") or ""),
                "frozen_level": frozen,
                "classification": item.get("classification"),
            }
    expected = {
        "PRECONSOLIDATION": EXPECTED_PRECONSOLIDATION_TARGETS,
        "EXACT_OHLC_SELECTION": EXPECTED_EXACT_OHLC_SELECTION_TARGETS,
        "NEAR_OHLC": EXPECTED_NEAR_OHLC_TARGETS,
        "NO_OHLC": EXPECTED_NO_OHLC_TARGETS,
    }
    actual = {k: len(v) for k, v in groups.items()}
    if actual != expected:
        raise SystemExit(f"FAIL CLOSED: .2.14 target extraction drift expected={expected} actual={actual}")
    return groups

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = (
        (root / args.bundle_root).resolve()
        if not Path(args.bundle_root).is_absolute()
        else Path(args.bundle_root)
    )
    output = (
        (root / args.output).resolve()
        if not Path(args.output).is_absolute()
        else Path(args.output)
    )

    report5214_path = require_file(root, REPORT_5214_REL, EXPECTED_REPORT_5214_SHA256,
                                   "M77.19.6.5.2.14 report")
    runner5214_path = require_file(root, RUNNER_5214_REL, EXPECTED_RUNNER_5214_SHA256,
                                   "M77.19.6.5.2.14 runner")
    require_file(root, RUNNER_5213_REL, EXPECTED_RUNNER_5213_SHA256,
                 "M77.19.6.5.2.13.1 runner")
    runner529_path = require_file(root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256,
                                  "M77.19.6.5.2.9.1 runner")
    native_path = require_file(root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256,
                               "native replay runner")

    report5214 = load_json(report5214_path)
    authority5214 = validate_5214(report5214)
    targets = collect_targets(report5214)

    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5215")
    native = import_module_from_path(native_path, "m77_native_5215")
    if not hasattr(helper529, "normalize_rows"):
        raise SystemExit("FAIL CLOSED: pinned .2.9.1 runner missing normalize_rows")

    sessions = load_spy_sessions()
    bundle_paths = sorted((bundle_root / "monthly").glob("*.json"))
    if len(bundle_paths) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(bundle_paths)}")

    arm_totals = {
        arm: {
            "exact_frozen_match_count": 0,
            "missing_beyond_0_3pct_count": 0,
            "preconsolidation_target_recovered_count": 0,
            "exact_ohlc_selection_target_recovered_count": 0,
            "near_ohlc_target_recovered_count": 0,
            "no_ohlc_target_recovered_count": 0,
        }
        for arm in ARMS
    }
    records = []

    for path in bundle_paths:
        bundle = load_json(path)
        rows = helper529.normalize_rows(bundle)
        frozen = bundle.get("frozen_profile")
        identity = bundle.get("prediction_identity")
        if not isinstance(frozen, dict) or not isinstance(identity, dict):
            raise SystemExit(f"FAIL CLOSED: malformed bundle authority: {path}")

        symbol = str(identity.get("symbol") or "")
        as_of = dt.date.fromisoformat(str(identity.get("as_of"))[:10])
        frozen_support = list(frozen.get("support_levels") or [])
        frozen_resistance = list(frozen.get("resistance_levels") or [])

        probe = native.StockIntelligenceService()
        level_source = inspect.getsource(type(probe.levels))
        if hashlib.sha256(level_source.encode()).hexdigest() != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
            raise SystemExit("FAIL CLOSED: LevelIntelligenceService source SHA drift")
        sr_source = inspect.getsource(type(probe.levels.sr))
        if hashlib.sha256(sr_source.encode()).hexdigest() != EXPECTED_SR_SOURCE_SHA256:
            raise SystemExit("FAIL CLOSED: SupportResistanceEngine source SHA drift")
        sr_module = importlib.import_module(type(probe.levels.sr).__module__)

        arm_results = {}
        for arm in ARMS:
            service = native.StockIntelligenceService()
            if arm != "NATIVE_CONTROL":
                service.levels.sr.analyze = build_arm_analyze(sr_module, arm)
            profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
            if profile is None:
                raise RuntimeError(f"{arm} profile ineligible for {symbol}")

            produced = {
                "support": list(profile.support_levels or []),
                "resistance": list(profile.resistance_levels or []),
            }
            frozen_by_side = {
                "support": frozen_support,
                "resistance": frozen_resistance,
            }

            exact_total = sum(
                exact_count(frozen_by_side[side], produced[side])
                for side in ("support", "resistance")
            )
            missing_total = sum(
                len(frozen_missing(frozen_by_side[side], produced[side]))
                for side in ("support", "resistance")
            )
            arm_totals[arm]["exact_frozen_match_count"] += exact_total
            arm_totals[arm]["missing_beyond_0_3pct_count"] += missing_total

            recovered = {g: [] for g in targets}
            for group, group_targets in targets.items():
                for key, target in group_targets.items():
                    if key[0] != symbol:
                        continue
                    side = key[1]
                    fp = float(key[3])
                    if any(
                        rel_distance(level_price(x), fp) < LEVEL_REACHABILITY_THRESHOLD
                        for x in produced[side]
                    ):
                        recovered[group].append({
                            "symbol": symbol,
                            "side": side,
                            "timeframe": key[2],
                            "price": fp,
                        })

            arm_totals[arm]["preconsolidation_target_recovered_count"] += len(recovered["PRECONSOLIDATION"])
            arm_totals[arm]["exact_ohlc_selection_target_recovered_count"] += len(recovered["EXACT_OHLC_SELECTION"])
            arm_totals[arm]["near_ohlc_target_recovered_count"] += len(recovered["NEAR_OHLC"])
            arm_totals[arm]["no_ohlc_target_recovered_count"] += len(recovered["NO_OHLC"])

            arm_results[arm] = {
                "exact_frozen_match_count": exact_total,
                "missing_beyond_0_3pct_count": missing_total,
                "recovered_targets": recovered,
            }

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "bundle": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "arms": arm_results,
        })

    if arm_totals["NATIVE_CONTROL"]["missing_beyond_0_3pct_count"] != EXPECTED_NATIVE_MISSING:
        raise SystemExit(
            "FAIL CLOSED: native missing authority drift "
            f"{arm_totals['NATIVE_CONTROL']['missing_beyond_0_3pct_count']}"
        )
    if arm_totals["NO_TOP12_BASELINE"]["missing_beyond_0_3pct_count"] != EXPECTED_NO_TOP12_RESIDUAL:
        raise SystemExit(
            "FAIL CLOSED: NO_TOP12 baseline residual authority drift "
            f"{arm_totals['NO_TOP12_BASELINE']['missing_beyond_0_3pct_count']}"
        )

    baseline = arm_totals["NO_TOP12_BASELINE"]
    for arm in ARMS:
        arm_totals[arm]["missing_reduction_vs_no_top12"] = (
            baseline["missing_beyond_0_3pct_count"]
            - arm_totals[arm]["missing_beyond_0_3pct_count"]
        )
        arm_totals[arm]["exact_gain_vs_no_top12"] = (
            arm_totals[arm]["exact_frozen_match_count"]
            - baseline["exact_frozen_match_count"]
        )

    causal_arms = [a for a in ARMS if a not in ("NATIVE_CONTROL", "NO_TOP12_BASELINE")]
    ranking = sorted(
        causal_arms,
        key=lambda a: (
            -arm_totals[a]["preconsolidation_target_recovered_count"],
            -arm_totals[a]["missing_reduction_vs_no_top12"],
            -arm_totals[a]["exact_gain_vs_no_top12"],
            a,
        ),
    )
    winner = ranking[0]
    w = arm_totals[winner]

    if w["preconsolidation_target_recovered_count"] > 0:
        conclusion = "POST_CANDIDATE_CONSOLIDATION_SEMANTICS_CAUSALLY_RESTORE_PRECONSOLIDATION_TARGETS"
        next_step = "BUILD_M77_19_6_5_2_16_WINNING_CONSOLIDATION_SEMANTIC_EXACT_PARITY_REPLAY"
    else:
        conclusion = "POST_CANDIDATE_CONSOLIDATION_SEMANTICS_DO_NOT_RESTORE_PRECONSOLIDATION_TARGETS"
        next_step = "BUILD_M77_19_6_5_2_16_CANDIDATE_TO_LEVEL_TRANSFORMATION_PROVENANCE_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5214": authority5214,
        "monthly_bundle_count": len(records),
        "predeclared_arms": list(ARMS),
        "arm_summaries": arm_totals,
        "ranking": ranking,
        "winner_analysis": {
            "winner": winner,
            "winner_preconsolidation_target_recovered_count": w["preconsolidation_target_recovered_count"],
            "winner_missing_reduction_vs_no_top12": w["missing_reduction_vs_no_top12"],
            "winner_exact_gain_vs_no_top12": w["exact_gain_vs_no_top12"],
            "no_top12_baseline_missing_count": baseline["missing_beyond_0_3pct_count"],
            "no_top12_baseline_exact_count": baseline["exact_frozen_match_count"],
        },
        "forensic_conclusion": conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
        "records": records,
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_control_unmodified": True,
            "no_top12_baseline_forensic_only": True,
            "one_factor_causal_arms_only": True,
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
            "frozen_profile_scoring_authority_only": True,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_14_report": {
                "path": str(report5214_path),
                "sha256": EXPECTED_REPORT_5214_SHA256,
            },
            "m77_19_6_5_2_14_runner": {
                "path": str(runner5214_path),
                "sha256": EXPECTED_RUNNER_5214_SHA256,
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

    print("=== M77.19.6.5.2.15 POST-CANDIDATE CONSOLIDATION SEMANTICS CAUSAL REPLAY ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5214:", authority5214)
    print("monthly_bundle_count:", len(records))
    print("predeclared_arms:", list(ARMS))
    for arm in ARMS:
        print(arm, arm_totals[arm])
    print("ranking:", ranking)
    print("winner_analysis:", report["winner_analysis"])
    print("forensic_conclusion:", conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
