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
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.19-NATIVE-OBSERVABLE-CONSOLIDATION-TRIGGER-CAUSAL-REPLAY-1.0"

REPORT_5218_REL = "reports/m77_19_6_5_2_18_minimal_generalizable_consolidation_semantic_forensics.json"
EXPECTED_REPORT_5218_SHA256 = "bc2c4f7411698d7ad25ba7fa85b384d4431d666547a09c4be3126ecfc91cd8aa"

RUNNER_5218_REL = "scripts/run_m77_19_6_5_2_18_minimal_generalizable_consolidation_semantic_forensics.py"
EXPECTED_RUNNER_5218_SHA256 = "979592ee06af3c5668f386f0e89f0d0b47633b0724be7eaeb7820ef703353818"

REPORT_5216_REL = "reports/m77_19_6_5_2_16_target_cluster_ancestry_provenance_trace.json"
EXPECTED_REPORT_5216_SHA256 = "14d27a0b77de03c306baa76f4b1178201f97305612f32f84e9c97ce2b8c41752"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"
EXPECTED_SR_SOURCE_SHA256 = "e960e1c5dfc3b8572d4bd4a321a2706490a4b52e92979a1c463ff54a58ac4213"

PARITY_TOLERANCE = 1e-9
LEVEL_REACHABILITY_THRESHOLD = 0.003
NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35

EXPECTED_MONTHLY_BUNDLE_COUNT = 48
EXPECTED_NATIVE_EXACT = 1338
EXPECTED_NATIVE_MISSING = 67

TARGETS = (
    ("AES", "resistance", 25.61),
    ("ANET", "support", 22.8919),
    ("ATO", "resistance", 103.405),
)

ARMS = (
    "NATIVE_CONTROL",
    "OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE",
    "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT",
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

def validate_5218(report: dict[str, Any]) -> None:
    summary = report.get("classification_summary") or {}
    ga = report.get("generalization_assessment") or {}
    if summary.get("exact_classification_count") != 3:
        raise SystemExit("FAIL CLOSED: .2.18 exact classification count drift")
    if summary.get("ambiguous_count") != 0 or summary.get("unresolved_count") != 0:
        raise SystemExit("FAIL CLOSED: .2.18 ambiguity/unresolved drift")
    if ga.get("symbol_identity_free") is not True:
        raise SystemExit("FAIL CLOSED: .2.18 symbol-identity-free gate drift")
    if ga.get("frozen_target_ancestry_required") is not True:
        raise SystemExit("FAIL CLOSED: .2.18 frozen ancestry gate drift")
    if ga.get("native_observable_only") is not False:
        raise SystemExit("FAIL CLOSED: .2.18 native-observable gate drift")
    if ga.get("production_generalizable_semantic_certified") is not False:
        raise SystemExit("FAIL CLOSED: .2.18 production generalization drift")
    if report.get("candidate_semantic_promoted") is not False:
        raise SystemExit("FAIL CLOSED: .2.18 semantic promotion drift")
    if report.get("production_authority_effect") is not False:
        raise SystemExit("FAIL CLOSED: .2.18 production authority drift")

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

def exact(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE

def rel_distance(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))

def level_price(x: Any) -> float:
    value = x.get("price") if isinstance(x, dict) else getattr(x, "price", None)
    if value is None:
        raise ValueError("level missing price")
    return float(value)

def frozen_side(profile: dict[str, Any], side: str) -> list[Any]:
    return list(profile.get("support_levels" if side == "support" else "resistance_levels") or [])

def produced_side(profile: Any, side: str) -> list[Any]:
    return list(profile.support_levels or []) if side == "support" else list(profile.resistance_levels or [])

def exact_count(frozen: list[Any], produced: list[Any]) -> int:
    pp = [level_price(x) for x in produced]
    return sum(1 for x in frozen if any(exact(level_price(x), p) for p in pp))

def missing_count(frozen: list[Any], produced: list[Any]) -> int:
    pp = [level_price(x) for x in produced]
    return sum(
        1 for x in frozen
        if not any(rel_distance(level_price(x), p) < LEVEL_REACHABILITY_THRESHOLD for p in pp)
    )

def build_observable_analyze(sr_module, arm: str):
    PriceLevel = sr_module.PriceLevel
    _rows = sr_module._rows
    _atr = sr_module._atr

    if arm == "NATIVE_CONTROL":
        return None

    def analyze(timeframe, data):
        rows = _rows(data)
        n = len(rows)
        if n < 20:
            return [], []

        atr = max(_atr(rows), 1e-9)
        native_merge_distance = atr * NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER
        candidates = []

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
        seed_price: dict[int, float] = {}
        preserved_seeds: list[tuple[str, float, int]] = []

        for typ, price, idx in candidates:
            eligible = []
            for pos, x in enumerate(out):
                if x.level_type != typ:
                    continue
                abs_gap = abs(float(x.price) - float(price))
                if abs_gap <= native_merge_distance:
                    eligible.append((pos, x, abs_gap))

            found = eligible[0] if eligible else None

            if found is None:
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
                seed_price[len(out)-1] = float(price)
                continue

            pos, x, _ = found
            observable_gap = rel_distance(float(x.price), float(price))

            if (
                arm == "OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE"
                and observable_gap >= LEVEL_REACHABILITY_THRESHOLD
            ):
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
                        {
                            "age_bars": age,
                            "research_trigger": "OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE",
                        },
                        [timeframe],
                    )
                )
                seed_price[len(out)-1] = float(price)
                continue

            before = float(x.price)
            after = (float(x.price) * x.touch_count + float(price)) / (x.touch_count + 1)
            x.price = after
            x.touch_count += 1
            x.strength = min(100, x.strength + 8)
            x.confluence_score = min(100, x.confluence_score + 10)

            if arm == "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT":
                seed = seed_price.get(pos, before)
                if rel_distance(after, seed) >= LEVEL_REACHABILITY_THRESHOLD:
                    preserved_seeds.append((typ, seed, idx))

        if arm == "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT":
            existing = [(x.level_type, float(x.price)) for x in out]
            for typ, price, idx in preserved_seeds:
                if any(t == typ and exact(p, price) for t, p in existing):
                    continue
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
                        {
                            "age_bars": age,
                            "research_trigger": "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT",
                        },
                        [timeframe],
                    )
                )
                existing.append((typ, float(price)))

        out.sort(key=lambda x: (-x.strength, x.price))
        # Native top-12 retention remains fixed.
        sup = [x for x in out if x.level_type == "SUPPORT"][:12]
        res = [x for x in out if x.level_type == "RESISTANCE"][:12]
        return sup, res

    return analyze

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    bundle_root = (root / args.bundle_root).resolve() if not Path(args.bundle_root).is_absolute() else Path(args.bundle_root)
    output = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    report5218_path = require_file(root, REPORT_5218_REL, EXPECTED_REPORT_5218_SHA256, "M77.19.6.5.2.18 report")
    require_file(root, RUNNER_5218_REL, EXPECTED_RUNNER_5218_SHA256, "M77.19.6.5.2.18 runner")
    report5216_path = require_file(root, REPORT_5216_REL, EXPECTED_REPORT_5216_SHA256, "M77.19.6.5.2.16 report")
    runner529_path = require_file(root, RUNNER_529_REL, EXPECTED_RUNNER_529_SHA256, "M77.19.6.5.2.9.1 runner")
    native_path = require_file(root, NATIVE_RUNNER_REL, EXPECTED_NATIVE_RUNNER_SHA256, "native replay runner")

    report5218 = load_json(report5218_path)
    validate_5218(report5218)
    report5216 = load_json(report5216_path)

    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5219")
    native = import_module_from_path(native_path, "m77_native_5219")
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
            f"FAIL CLOSED: expected {EXPECTED_MONTHLY_BUNDLE_COUNT} monthly bundles, found {len(bundle_paths)}"
        )

    target_lookup = {(s, side): price for s, side, price in TARGETS}
    arm_totals = {
        arm: {
            "exact_frozen_match_count": 0,
            "missing_beyond_0_3pct_count": 0,
            "target_recovered_symbols": [],
        }
        for arm in ARMS
    }
    records = []

    for path in bundle_paths:
        bundle = load_json(path)
        identity = bundle.get("prediction_identity") or {}
        frozen = bundle.get("frozen_profile")
        if not isinstance(frozen, dict):
            raise SystemExit(f"FAIL CLOSED: frozen_profile missing: {path}")
        symbol = str(identity.get("symbol") or "")
        as_of = dt.date.fromisoformat(str(identity.get("as_of"))[:10])
        rows = helper529.normalize_rows(bundle)

        arm_records = {}
        for arm in ARMS:
            service = native.StockIntelligenceService()
            if arm != "NATIVE_CONTROL":
                service.levels.sr.analyze = build_observable_analyze(sr_module, arm)

            profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
            if profile is None:
                raise SystemExit(f"FAIL CLOSED: {arm} profile ineligible for {symbol}")

            exact_total = 0
            missing_total = 0
            for side in ("support", "resistance"):
                ff = frozen_side(frozen, side)
                pp = produced_side(profile, side)
                exact_total += exact_count(ff, pp)
                missing_total += missing_count(ff, pp)

                target_price = target_lookup.get((symbol, side))
                if target_price is not None:
                    reachable = any(
                        rel_distance(level_price(x), target_price) < LEVEL_REACHABILITY_THRESHOLD
                        for x in pp
                    )
                    if reachable:
                        arm_totals[arm]["target_recovered_symbols"].append(symbol)

            arm_totals[arm]["exact_frozen_match_count"] += exact_total
            arm_totals[arm]["missing_beyond_0_3pct_count"] += missing_total
            arm_records[arm] = {
                "exact_frozen_match_count": exact_total,
                "missing_beyond_0_3pct_count": missing_total,
            }

        records.append({
            "symbol": symbol,
            "as_of": str(as_of),
            "arms": arm_records,
        })

    native_summary = arm_totals["NATIVE_CONTROL"]
    if native_summary["exact_frozen_match_count"] != EXPECTED_NATIVE_EXACT:
        raise SystemExit(
            f"FAIL CLOSED: native exact authority drift expected={EXPECTED_NATIVE_EXACT} "
            f"actual={native_summary['exact_frozen_match_count']}"
        )
    if native_summary["missing_beyond_0_3pct_count"] != EXPECTED_NATIVE_MISSING:
        raise SystemExit(
            f"FAIL CLOSED: native missing authority drift expected={EXPECTED_NATIVE_MISSING} "
            f"actual={native_summary['missing_beyond_0_3pct_count']}"
        )

    for arm in ARMS:
        arm_totals[arm]["target_recovered_symbols"] = sorted(set(arm_totals[arm]["target_recovered_symbols"]))
        arm_totals[arm]["target_recovered_count"] = len(arm_totals[arm]["target_recovered_symbols"])
        arm_totals[arm]["exact_gain_vs_native"] = (
            arm_totals[arm]["exact_frozen_match_count"] - native_summary["exact_frozen_match_count"]
        )
        arm_totals[arm]["missing_reduction_vs_native"] = (
            native_summary["missing_beyond_0_3pct_count"] - arm_totals[arm]["missing_beyond_0_3pct_count"]
        )

    causal_arms = [a for a in ARMS if a != "NATIVE_CONTROL"]
    ranking = sorted(
        causal_arms,
        key=lambda a: (
            arm_totals[a]["target_recovered_count"],
            arm_totals[a]["missing_reduction_vs_native"],
            arm_totals[a]["exact_gain_vs_native"],
        ),
        reverse=True,
    )
    winner = ranking[0]
    w = arm_totals[winner]

    globally_non_degrading = (
        w["missing_beyond_0_3pct_count"] <= native_summary["missing_beyond_0_3pct_count"]
        and w["exact_frozen_match_count"] >= native_summary["exact_frozen_match_count"]
    )
    all_three_targets_recovered = set(w["target_recovered_symbols"]) == {"AES", "ANET", "ATO"}

    if all_three_targets_recovered and globally_non_degrading:
        conclusion = "NATIVE_OBSERVABLE_TRIGGER_RECOVERS_ALL_CAUSAL_TARGETS_WITHOUT_GLOBAL_PARITY_DEGRADATION"
        next_step = "BUILD_M77_19_6_5_2_20_NATIVE_OBSERVABLE_TRIGGER_STRICT_PARITY_CERTIFICATION"
    elif all_three_targets_recovered:
        conclusion = "NATIVE_OBSERVABLE_TRIGGER_RECOVERS_ALL_CAUSAL_TARGETS_BUT_GLOBAL_PARITY_TRADEOFF_REMAINS"
        next_step = "BUILD_M77_19_6_5_2_20_NATIVE_OBSERVABLE_TRIGGER_COLLATERAL_IMPACT_FORENSICS"
    else:
        conclusion = "NO_PREDECLARED_NATIVE_OBSERVABLE_TRIGGER_CLOSES_ALL_CAUSAL_TARGETS"
        next_step = "BUILD_M77_19_6_5_2_20_NATIVE_OBSERVABLE_TRIGGER_RESIDUAL_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5218": {
            "report_sha256": EXPECTED_REPORT_5218_SHA256,
            "runner_sha256": EXPECTED_RUNNER_5218_SHA256,
            "identity_free_classification_closed_3_of_3": True,
            "frozen_target_ancestry_still_required_upstream": True,
            "production_generalization_not_certified_upstream": True,
            "pass": True,
        },
        "monthly_bundle_count": len(bundle_paths),
        "predeclared_arms": list(ARMS),
        "arm_summaries": arm_totals,
        "ranking": ranking,
        "winner_analysis": {
            "winner": winner,
            "all_three_targets_recovered": all_three_targets_recovered,
            "globally_non_degrading": globally_non_degrading,
            "target_recovered_symbols": w["target_recovered_symbols"],
            "exact_gain_vs_native": w["exact_gain_vs_native"],
            "missing_reduction_vs_native": w["missing_reduction_vs_native"],
        },
        "forensic_conclusion": conclusion,
        "native_observable_trigger_uses_frozen_target_identity": False,
        "native_observable_trigger_uses_symbol_identity": False,
        "native_observable_trigger_uses_historical_answer": False,
        "candidate_semantic_promoted": False,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
        "records": records,
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
            "observable_trigger_threshold_source": "EXISTING_NATIVE_LEVEL_MERGE_THRESHOLD",
            "threshold_search_or_optimization": False,
            "symbol_specific_rules_prohibited": True,
            "frozen_target_identity_prohibited": True,
            "historical_answer_leakage_prohibited": True,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "candidate_semantic_promoted": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.19 NATIVE OBSERVABLE CONSOLIDATION TRIGGER CAUSAL REPLAY ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5218:", report["authority_5218"])
    print("monthly_bundle_count:", len(bundle_paths))
    print("predeclared_arms:", list(ARMS))
    for arm in ARMS:
        print(arm, arm_totals[arm])
    print("ranking:", ranking)
    print("winner_analysis:", report["winner_analysis"])
    print("forensic_conclusion:", conclusion)
    print("native_observable_trigger_uses_frozen_target_identity: False")
    print("native_observable_trigger_uses_symbol_identity: False")
    print("native_observable_trigger_uses_historical_answer: False")
    print("candidate_semantic_promoted: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
