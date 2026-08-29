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

VERSION = "M77.19.6.5.2.13-SUPPORT-RESISTANCE-CANDIDATE-ALGORITHM-CAUSAL-HYPOTHESIS-REPLAY-1.0"

REPORT_5212_REL = "reports/m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.json"
EXPECTED_REPORT_5212_SHA256 = "e334a12928eda8da1109e14ce68f92a1ceb92fd8411f04842099bedb63d6d72c"

RUNNER_5212_REL = "scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
EXPECTED_RUNNER_5212_SHA256 = "aaa9779e970a14a697d43f297954b7b2cc399b7e926cf805c334d3f4cea979a1"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

PARITY_TOLERANCE = 1e-9
LEVEL_MERGE_THRESHOLD = 0.003

ARMS = (
    "NATIVE_CONTROL",
    "NO_TOP12_RETENTION",
    "NO_INTERNAL_ATR_CONSOLIDATION",
    "PIVOT_RADIUS_1",
    "PIVOT_RADIUS_3",
    "ADD_ROLLING_WINDOW_10",
    "ADD_ROLLING_WINDOW_200",
)

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

def exact(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE

def rel_distance(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))

def level_price(x: Any) -> float:
    value = x.get("price") if isinstance(x, dict) else getattr(x, "price", None)
    if value is None:
        raise ValueError("level missing price")
    return float(value)

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

def validate_5212(report: dict[str, Any]) -> dict[str, Any]:
    ss = report.get("support_summary") or {}
    rs = report.get("resistance_summary") or {}
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "RAW_CANDIDATE_GENERATION_HAS_MISSING_OR_NONREACHABLE_FROZEN_LEVELS",
        "support_missing_positive": ss.get("no_raw_candidate_within_0_3pct_count", 0) > 0,
        "resistance_missing_positive": rs.get("no_raw_candidate_within_0_3pct_count", 0) > 0,
        "candidate_generation_unmodified": (report.get("governance") or {}).get(
            "native_support_resistance_candidate_generation_unmodified"
        ) is True,
        "merge_threshold_fixed": (report.get("governance") or {}).get("merge_threshold") == 0.003,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.12 authority validation failed: {checks}")
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

def arm_spec(name: str) -> dict[str, Any]:
    native = {
        "pivot_radius": 2,
        "rolling_windows": (20, 50, 100),
        "internal_atr_consolidation": True,
        "top_n_per_side": 12,
    }
    if name == "NATIVE_CONTROL":
        return native
    spec = dict(native)
    if name == "NO_TOP12_RETENTION":
        spec["top_n_per_side"] = None
    elif name == "NO_INTERNAL_ATR_CONSOLIDATION":
        spec["internal_atr_consolidation"] = False
    elif name == "PIVOT_RADIUS_1":
        spec["pivot_radius"] = 1
    elif name == "PIVOT_RADIUS_3":
        spec["pivot_radius"] = 3
    elif name == "ADD_ROLLING_WINDOW_10":
        spec["rolling_windows"] = (10, 20, 50, 100)
    elif name == "ADD_ROLLING_WINDOW_200":
        spec["rolling_windows"] = (20, 50, 100, 200)
    else:
        raise ValueError(name)
    return spec

def make_hypothesis_analyze(original, sr_module, spec: dict[str, Any]):
    if spec == arm_spec("NATIVE_CONTROL"):
        return original

    PriceLevel = sr_module.PriceLevel
    _rows = sr_module._rows
    _atr = sr_module._atr
    radius = int(spec["pivot_radius"])
    windows = tuple(int(x) for x in spec["rolling_windows"])
    consolidate = bool(spec["internal_atr_consolidation"])
    top_n = spec["top_n_per_side"]

    def analyze(timeframe, data):
        rows = _rows(data)
        n = len(rows)
        if n < 20:
            return [], []
        atr = max(_atr(rows), 1e-9)
        candidates = []

        for i in range(radius, n - radius):
            h = float(rows[i]["high"])
            l = float(rows[i]["low"])
            window = rows[i-radius:i+radius+1]
            if h >= max(float(x["high"]) for x in window):
                candidates.append(("RESISTANCE", h, i))
            if l <= min(float(x["low"]) for x in window):
                candidates.append(("SUPPORT", l, i))

        for w in windows:
            if n >= w:
                candidates += [
                    ("RESISTANCE", max(float(x["high"]) for x in rows[-w:]), n-1),
                    ("SUPPORT", min(float(x["low"]) for x in rows[-w:]), n-1),
                ]

        out = []
        for typ, price, idx in candidates:
            found = None
            if consolidate:
                found = next(
                    (
                        x for x in out
                        if x.level_type == typ and abs(x.price-price) <= atr * .35
                    ),
                    None,
                )
            if found:
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

        out.sort(key=lambda x: (-x.strength, x.price))
        sup = [x for x in out if x.level_type == "SUPPORT"]
        res = [x for x in out if x.level_type == "RESISTANCE"]
        if top_n is not None:
            sup = sup[:int(top_n)]
            res = res[:int(top_n)]
        return sup, res

    return analyze

def compare_side(native_items: list[Any], arm_items: list[Any], frozen_items: list[Any]) -> dict[str, Any]:
    native_prices = [level_price(x) for x in native_items]
    arm_prices = [level_price(x) for x in arm_items]
    frozen_prices = [level_price(x) for x in frozen_items]

    exact_count = 0
    near_count = 0
    missing_count = 0
    for fp in frozen_prices:
        if any(exact(fp, ap) for ap in arm_prices):
            exact_count += 1
        elif any(rel_distance(ap, fp) < LEVEL_MERGE_THRESHOLD for ap in arm_prices):
            near_count += 1
        else:
            missing_count += 1

    native_exact_count = sum(
        1 for fp in frozen_prices if any(exact(fp, np) for np in native_prices)
    )
    native_missing_count = sum(
        1 for fp in frozen_prices
        if not any(rel_distance(np, fp) < LEVEL_MERGE_THRESHOLD for np in native_prices)
    )

    return {
        "frozen_count": len(frozen_prices),
        "arm_count": len(arm_prices),
        "exact_frozen_match_count": exact_count,
        "within_0_3pct_but_not_exact_count": near_count,
        "missing_beyond_0_3pct_count": missing_count,
        "native_exact_frozen_match_count": native_exact_count,
        "native_missing_beyond_0_3pct_count": native_missing_count,
        "exact_gain_vs_native": exact_count - native_exact_count,
        "missing_reduction_vs_native": native_missing_count - missing_count,
        "exact_price_set": (
            len(arm_prices) == len(frozen_prices)
            and all(any(exact(fp, ap) for ap in arm_prices) for fp in frozen_prices)
            and all(any(exact(ap, fp) for fp in frozen_prices) for ap in arm_prices)
        ),
    }

def summarize(records: list[dict[str, Any]], arm: str, side: str) -> dict[str, Any]:
    exact = near = missing = frozen = exact_sets = 0
    native_exact = native_missing = 0
    for r in records:
        x = r["arms"][arm][side]
        frozen += x["frozen_count"]
        exact += x["exact_frozen_match_count"]
        near += x["within_0_3pct_but_not_exact_count"]
        missing += x["missing_beyond_0_3pct_count"]
        native_exact += x["native_exact_frozen_match_count"]
        native_missing += x["native_missing_beyond_0_3pct_count"]
        exact_sets += int(x["exact_price_set"])
    return {
        "bundle_count": len(records),
        "frozen_level_total": frozen,
        "exact_frozen_match_count": exact,
        "within_0_3pct_but_not_exact_count": near,
        "missing_beyond_0_3pct_count": missing,
        "exact_price_set_bundle_count": exact_sets,
        "native_exact_frozen_match_count": native_exact,
        "native_missing_beyond_0_3pct_count": native_missing,
        "exact_gain_vs_native": exact - native_exact,
        "missing_reduction_vs_native": native_missing - missing,
    }

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

    report5212_path = require_file(
        root, REPORT_5212_REL, EXPECTED_REPORT_5212_SHA256, "M77.19.6.5.2.12 report"
    )
    runner5212_path = require_file(
        root, RUNNER_5212_REL, EXPECTED_RUNNER_5212_SHA256, "M77.19.6.5.2.12.3 runner"
    )
    runner529_path = require_file(
        root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256, "M77.19.6.5.2.9.1 runner"
    )
    native_path = require_file(
        root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256, "native replay runner"
    )

    report5212 = load_json(report5212_path)
    authority5212 = validate_5212(report5212)
    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5213")
    native = import_module_from_path(native_path, "m77_native_5213")
    if not hasattr(helper529, "normalize_rows"):
        raise SystemExit("FAIL CLOSED: pinned .2.9 runner missing normalize_rows")

    sessions = load_spy_sessions()
    bundle_paths = sorted((bundle_root / "monthly").glob("*.json"))
    if len(bundle_paths) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(bundle_paths)}")

    records = []
    sr_source_sha = None

    for path in bundle_paths:
        bundle = load_json(path)
        rows = helper529.normalize_rows(bundle)

        frozen = bundle.get("frozen_profile")
        identity = bundle.get("prediction_identity")
        if not isinstance(frozen, dict):
            raise SystemExit(f"FAIL CLOSED: bundle missing frozen_profile: {path}")
        if not isinstance(identity, dict):
            raise SystemExit(f"FAIL CLOSED: bundle missing prediction_identity: {path}")

        symbol = str(identity.get("symbol") or "")
        as_of_raw = identity.get("as_of")
        if not symbol or not as_of_raw:
            raise SystemExit(f"FAIL CLOSED: incomplete prediction_identity: {path}")
        as_of = dt.date.fromisoformat(str(as_of_raw)[:10])

        control_service = native.StockIntelligenceService()
        level_source = inspect.getsource(type(control_service.levels))
        level_sha = hashlib.sha256(level_source.encode()).hexdigest()
        if level_sha != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
            raise SystemExit(
                f"FAIL CLOSED: LevelIntelligenceService SHA drift: "
                f"expected={EXPECTED_LEVEL_SERVICE_SOURCE_SHA256} actual={level_sha}"
            )
        sr_source = inspect.getsource(type(control_service.levels.sr))
        this_sr_sha = hashlib.sha256(sr_source.encode()).hexdigest()
        if this_sr_sha != EXPECTED_SR_SOURCE_SHA256:
            raise SystemExit(
                f"FAIL CLOSED: SupportResistanceEngine SHA drift: "
                f"expected={EXPECTED_SR_SOURCE_SHA256} actual={this_sr_sha}"
            )
        sr_source_sha = this_sr_sha

        control_profile = native.call_profile(
            control_service, symbol, rows, as_of, sessions, 300, 750
        )
        if control_profile is None:
            raise RuntimeError(f"native control profile ineligible for {symbol}")

        native_support = list(control_profile.support_levels or [])
        native_resistance = list(control_profile.resistance_levels or [])
        frozen_support = list(frozen.get("support_levels") or [])
        frozen_resistance = list(frozen.get("resistance_levels") or [])

        arm_results = {}
        for arm in ARMS:
            if arm == "NATIVE_CONTROL":
                profile = control_profile
            else:
                service = native.StockIntelligenceService()
                sr_module = importlib.import_module(type(service.levels.sr).__module__)
                original = service.levels.sr.analyze
                service.levels.sr.analyze = make_hypothesis_analyze(
                    original, sr_module, arm_spec(arm)
                )
                profile = native.call_profile(
                    service, symbol, rows, as_of, sessions, 300, 750
                )
                if profile is None:
                    raise RuntimeError(f"{arm} profile ineligible for {symbol}")

            arm_results[arm] = {
                "support": compare_side(
                    native_support, list(profile.support_levels or []), frozen_support
                ),
                "resistance": compare_side(
                    native_resistance, list(profile.resistance_levels or []), frozen_resistance
                ),
                "profile_confidence_exact": exact(
                    float(profile.confidence), float(frozen.get("confidence") or 0.0)
                ),
            }

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "bundle": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "arms": arm_results,
        })

    arm_summaries = {}
    for arm in ARMS:
        support = summarize(records, arm, "support")
        resistance = summarize(records, arm, "resistance")
        confidence_exact = sum(
            int(r["arms"][arm]["profile_confidence_exact"]) for r in records
        )
        arm_summaries[arm] = {
            "spec": arm_spec(arm),
            "support": support,
            "resistance": resistance,
            "combined_exact_frozen_match_count":
                support["exact_frozen_match_count"] + resistance["exact_frozen_match_count"],
            "combined_missing_beyond_0_3pct_count":
                support["missing_beyond_0_3pct_count"] + resistance["missing_beyond_0_3pct_count"],
            "combined_missing_reduction_vs_native":
                support["missing_reduction_vs_native"] + resistance["missing_reduction_vs_native"],
            "combined_exact_gain_vs_native":
                support["exact_gain_vs_native"] + resistance["exact_gain_vs_native"],
            "profile_confidence_exact_count": confidence_exact,
        }

    def rank_key(arm: str):
        s = arm_summaries[arm]
        return (
            s["combined_missing_reduction_vs_native"],
            s["combined_exact_gain_vs_native"],
            s["support"]["exact_price_set_bundle_count"]
                + s["resistance"]["exact_price_set_bundle_count"],
            s["combined_exact_frozen_match_count"],
        )

    ranking = sorted(ARMS, key=rank_key, reverse=True)
    winner = ranking[0]
    native_key = rank_key("NATIVE_CONTROL")
    winner_key = rank_key(winner)

    if winner == "NATIVE_CONTROL" or winner_key <= native_key:
        conclusion = "NO_PREDECLARED_CANDIDATE_ALGORITHM_HYPOTHESIS_OUTPERFORMS_NATIVE"
        next_step = "BUILD_M77_19_6_5_2_14_CANDIDATE_INPUT_HISTORY_AND_RUNTIME_SEMANTICS_FORENSICS"
    elif arm_summaries[winner]["combined_missing_beyond_0_3pct_count"] == 0:
        conclusion = "PREDECLARED_CANDIDATE_ALGORITHM_HYPOTHESIS_CLOSES_FROZEN_LEVEL_REACHABILITY"
        next_step = "BUILD_M77_19_6_5_2_14_WINNING_CANDIDATE_ALGORITHM_FULL_CAUSAL_PARITY_REPLAY"
    else:
        conclusion = "PREDECLARED_CANDIDATE_ALGORITHM_HYPOTHESIS_PARTIALLY_RESTORES_FROZEN_LEVEL_REACHABILITY"
        next_step = "BUILD_M77_19_6_5_2_14_RESIDUAL_CANDIDATE_GENERATION_SEMANTICS_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5212": authority5212,
        "monthly_bundle_count": len(records),
        "predeclared_arms": list(ARMS),
        "arm_summaries": arm_summaries,
        "ranking": ranking,
        "winner_analysis": {
            "winner": winner,
            "winner_score": winner_key,
            "native_score": native_key,
            "winner_missing_reduction_vs_native":
                arm_summaries[winner]["combined_missing_reduction_vs_native"],
            "winner_exact_gain_vs_native":
                arm_summaries[winner]["combined_exact_gain_vs_native"],
        },
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
            "hypothesis_arms_research_only": True,
            "hypothesis_arms_predeclared": True,
            "threshold_search_or_optimization": False,
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
            "m77_19_6_5_2_12_report": {
                "path": str(report5212_path),
                "sha256": EXPECTED_REPORT_5212_SHA256,
            },
            "m77_19_6_5_2_12_3_runner": {
                "path": str(runner5212_path),
                "sha256": EXPECTED_RUNNER_5212_SHA256,
            },
            "native_runner": {
                "path": str(native_path),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
            "support_resistance_source_sha256": sr_source_sha,
            "level_service_source_sha256": EXPECTED_LEVEL_SERVICE_SOURCE_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.13 SUPPORT / RESISTANCE CANDIDATE ALGORITHM CAUSAL HYPOTHESIS REPLAY ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5212:", authority5212)
    print("monthly_bundle_count:", len(records))
    print("predeclared_arms:", list(ARMS))
    for arm in ARMS:
        s = arm_summaries[arm]
        print(arm, {
            "combined_exact_frozen_match_count": s["combined_exact_frozen_match_count"],
            "combined_missing_beyond_0_3pct_count": s["combined_missing_beyond_0_3pct_count"],
            "combined_missing_reduction_vs_native": s["combined_missing_reduction_vs_native"],
            "combined_exact_gain_vs_native": s["combined_exact_gain_vs_native"],
            "profile_confidence_exact_count": s["profile_confidence_exact_count"],
        })
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
