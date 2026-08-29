#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.11.1-HELPER529-BUNDLE-NORMALIZATION-REPAIR-1.0"

REPORT_5210_REL = "reports/m77_19_6_5_2_10_level_generation_input_and_selection_semantics_forensics.json"
EXPECTED_REPORT_5210_SHA256 = "dfc11d3e4f7c5c45cd47b68f6cccb9133da2f8afa0f253dfbb234ab0f27f0d51"

RUNNER_5210_REL = "scripts/run_m77_19_6_5_2_10_level_generation_input_and_selection_semantics_forensics.py"
EXPECTED_RUNNER_5210_SHA256 = "9e903c9ce752282e169a33c6beafc469af7650dd7647ba4c0788a953b764dc4c"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_RUNNER_529_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_LEVEL_SERVICE_SOURCE_SHA256 = "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490"

PARITY_TOLERANCE = 1e-9
MERGE_THRESHOLD = 0.003

ARMS = (
    "NATIVE_FIRST_ASCENDING",
    "LAST_ASCENDING",
    "ARITHMETIC_MEAN",
    "STRENGTH_WEIGHTED_MEAN",
    "CONFLUENCE_WEIGHTED_MEAN",
    "TOUCH_WEIGHTED_MEAN",
    "MAX_STRENGTH_CANDIDATE",
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

def validate_5210(report: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "LEVEL_GENERATION_DIVERGENCE_LOCALIZED_TO_CANDIDATE_PRICE_CALCULATION_OR_ROUNDING",
        "support_near_match": (report.get("support_summary") or {}).get(
            "frozen_nearest_within_0_5pct_pct", 0
        ) >= 95.0,
        "resistance_near_match": (report.get("resistance_summary") or {}).get(
            "frozen_nearest_within_0_5pct_pct", 0
        ) >= 95.0,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.10 authority validation failed: {checks}")
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
        rows = session.execute(
            text(
                """
                SELECT date
                FROM public.price_history
                WHERE symbol = 'SPY'
                ORDER BY date
                """
            )
        ).all()

    sessions: set[dt.date] = set()
    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        sessions.add(value)

    if not sessions:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")
    return sessions

def level_price(item: Any) -> float:
    if isinstance(item, dict):
        value = item.get("price")
    else:
        value = getattr(item, "price", None)
    if value is None:
        raise ValueError("level missing price")
    return float(value)

def numeric_attr(item: Any, name: str, default: float = 0.0) -> float:
    if isinstance(item, dict):
        value = item.get(name, default)
    else:
        value = getattr(item, name, default)
    try:
        return float(value)
    except Exception:
        return float(default)

def exact_price(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE

def cluster_native_membership(levels: list[Any]) -> list[list[Any]]:
    """
    Preserve native membership semantics exactly:
    sort ascending, then attach each candidate to the first existing cluster
    whose immutable anchor price is within the native 0.3% rule.
    """
    ordered = sorted(levels, key=level_price)
    clusters: list[list[Any]] = []
    anchors: list[float] = []

    for item in ordered:
        price = level_price(item)
        chosen = None
        for idx, anchor in enumerate(anchors):
            if abs(anchor - price) / max(1.0, price) < MERGE_THRESHOLD:
                chosen = idx
                break
        if chosen is None:
            clusters.append([item])
            anchors.append(price)
        else:
            clusters[chosen].append(item)

    return clusters

def weighted_mean(items: list[Any], field: str) -> float:
    weights = [max(0.0, numeric_attr(x, field, 0.0)) for x in items]
    total = sum(weights)
    if total <= 0:
        return sum(level_price(x) for x in items) / len(items)
    return sum(level_price(x) * w for x, w in zip(items, weights)) / total

def representative_price(cluster: list[Any], arm: str) -> float:
    ordered = sorted(cluster, key=level_price)

    if arm == "NATIVE_FIRST_ASCENDING":
        return level_price(ordered[0])
    if arm == "LAST_ASCENDING":
        return level_price(ordered[-1])
    if arm == "ARITHMETIC_MEAN":
        return sum(level_price(x) for x in ordered) / len(ordered)
    if arm == "STRENGTH_WEIGHTED_MEAN":
        return weighted_mean(ordered, "strength")
    if arm == "CONFLUENCE_WEIGHTED_MEAN":
        return weighted_mean(ordered, "confluence_score")
    if arm == "TOUCH_WEIGHTED_MEAN":
        return weighted_mean(ordered, "touch_count")
    if arm == "MAX_STRENGTH_CANDIDATE":
        winner = max(
            enumerate(ordered),
            key=lambda pair: (numeric_attr(pair[1], "strength"), -pair[0]),
        )[1]
        return level_price(winner)

    raise ValueError(f"unknown arm {arm}")

def replay_prices(raw_candidates: list[Any], arm: str) -> tuple[list[float], list[dict[str, Any]]]:
    clusters = cluster_native_membership(raw_candidates)
    cluster_records = []
    prices = []

    for cluster in clusters:
        rep = representative_price(cluster, arm)
        prices.append(rep)
        cluster_records.append(
            {
                "member_prices": [level_price(x) for x in cluster],
                "member_strengths": [numeric_attr(x, "strength") for x in cluster],
                "member_confluence_scores": [
                    numeric_attr(x, "confluence_score") for x in cluster
                ],
                "member_touch_counts": [numeric_attr(x, "touch_count") for x in cluster],
                "representative_price": rep,
            }
        )

    return prices, cluster_records

def compare_price_sets(candidate_prices: list[float], frozen_items: list[Any]) -> dict[str, Any]:
    frozen_prices = [level_price(x) for x in frozen_items]

    frozen_match_count = sum(
        1 for f in frozen_prices if any(exact_price(f, c) for c in candidate_prices)
    )
    candidate_match_count = sum(
        1 for c in candidate_prices if any(exact_price(c, f) for f in frozen_prices)
    )

    exact_set = (
        len(candidate_prices) == len(frozen_prices)
        and frozen_match_count == len(frozen_prices)
        and candidate_match_count == len(candidate_prices)
    )

    return {
        "candidate_count": len(candidate_prices),
        "frozen_count": len(frozen_prices),
        "frozen_exact_price_match_count": frozen_match_count,
        "candidate_exact_price_match_count": candidate_match_count,
        "exact_price_set": exact_set,
    }

def capture_raw_sr_candidates(service: Any):
    original = service.levels.sr.analyze
    capture: list[dict[str, Any]] = []

    def wrapped(timeframe, data):
        support, resistance = original(timeframe, data)
        capture.append(
            {
                "timeframe": str(timeframe),
                "support": copy.deepcopy(list(support or [])),
                "resistance": copy.deepcopy(list(resistance or [])),
            }
        )
        return support, resistance

    service.levels.sr.analyze = wrapped

    def restore():
        service.levels.sr.analyze = original

    return capture, restore

def run_native_profile(native, helper5210, symbol, rows, as_of, sessions):
    service = native.StockIntelligenceService()

    source = inspect.getsource(type(service.levels))
    actual_source_sha = hashlib.sha256(source.encode()).hexdigest()
    if actual_source_sha != EXPECTED_LEVEL_SERVICE_SOURCE_SHA256:
        raise SystemExit(
            "FAIL CLOSED: LevelIntelligenceService source drift: "
            f"expected={EXPECTED_LEVEL_SERVICE_SOURCE_SHA256} actual={actual_source_sha}"
        )

    capture, restore = capture_raw_sr_candidates(service)
    try:
        profile = native.call_profile(
            service,
            symbol,
            rows,
            as_of,
            sessions,
            300,
            750,
        )
    finally:
        restore()

    if profile is None:
        raise RuntimeError(f"native profile ineligible for {symbol}")

    return profile, capture

def flatten_candidates(capture: list[dict[str, Any]], side: str) -> list[Any]:
    result: list[Any] = []
    for item in capture:
        result.extend(item[side])
    return result

def arm_summary(records: list[dict[str, Any]], arm: str, side: str) -> dict[str, Any]:
    values = [r["arms"][arm][side] for r in records]
    frozen_total = sum(v["frozen_count"] for v in values)
    frozen_matches = sum(v["frozen_exact_price_match_count"] for v in values)
    return {
        "bundle_count": len(values),
        "exact_price_set_bundle_count": sum(1 for v in values if v["exact_price_set"]),
        "frozen_exact_price_match_count": frozen_matches,
        "frozen_level_total": frozen_total,
        "frozen_exact_price_match_pct": (
            100.0 * frozen_matches / frozen_total if frozen_total else 100.0
        ),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_11_level_selection_hypothesis_causal_replay.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    report5210_path = require_file(
        root,
        REPORT_5210_REL,
        EXPECTED_REPORT_5210_SHA256,
        "M77.19.6.5.2.10 report",
    )
    runner5210_path = require_file(
        root,
        RUNNER_5210_REL,
        EXPECTED_RUNNER_5210_SHA256,
        "M77.19.6.5.2.10 runner",
    )
    runner529_path = require_file(
        root,
        RUNNER_529_REL,
        EXPECTED_RUNNER_529_SHA256,
        "M77.19.6.5.2.9.1 repaired runner",
    )
    native_path = require_file(
        root,
        NATIVE_RUNNER_REL,
        EXPECTED_NATIVE_RUNNER_SHA256,
        "native replay runner",
    )

    report5210 = load_json(report5210_path)
    authority5210 = validate_5210(report5210)

    helper5210 = import_module_from_path(runner5210_path, "m77_helper_5210_for_5211")
    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5211")
    if not hasattr(helper529, "normalize_rows"):
        raise SystemExit("FAIL CLOSED: pinned M77.19.6.5.2.9 runner does not expose normalize_rows")
    native = import_module_from_path(native_path, "m77_native_5211")
    sessions = load_spy_sessions()

    monthly_files = sorted((root / args.bundle_root / "monthly").glob("*.json"))
    if len(monthly_files) != 48:
        raise SystemExit(
            f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}"
        )

    records = []

    for file_path in monthly_files:
        bundle = load_json(file_path)
        identity = bundle["prediction_identity"]
        frozen_profile = bundle["frozen_profile"]

        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(str(identity["as_of"])[:10])
        rows = helper529.normalize_rows(bundle)

        native_profile, raw_capture = run_native_profile(
            native,
            helper5210,
            symbol,
            rows,
            as_of,
            sessions,
        )

        raw_support = flatten_candidates(raw_capture, "support")
        raw_resistance = flatten_candidates(raw_capture, "resistance")

        arm_results = {}
        cluster_details = {}

        for arm in ARMS:
            support_prices, support_clusters = replay_prices(raw_support, arm)
            resistance_prices, resistance_clusters = replay_prices(raw_resistance, arm)

            arm_results[arm] = {
                "support": compare_price_sets(
                    support_prices,
                    list(frozen_profile.get("support_levels") or []),
                ),
                "resistance": compare_price_sets(
                    resistance_prices,
                    list(frozen_profile.get("resistance_levels") or []),
                ),
            }

            if arm == "NATIVE_FIRST_ASCENDING":
                cluster_details = {
                    "support": support_clusters,
                    "resistance": resistance_clusters,
                }

        records.append(
            {
                "bundle": str(file_path.relative_to(root)),
                "symbol": symbol,
                "as_of": as_of.isoformat(),
                "raw_candidate_counts": {
                    "support": len(raw_support),
                    "resistance": len(raw_resistance),
                    "by_timeframe": [
                        {
                            "timeframe": x["timeframe"],
                            "support": len(x["support"]),
                            "resistance": len(x["resistance"]),
                        }
                        for x in raw_capture
                    ],
                },
                "native_cluster_details": cluster_details,
                "arms": arm_results,
            }
        )

    summaries = {}
    for arm in ARMS:
        summaries[arm] = {
            "support": arm_summary(records, arm, "support"),
            "resistance": arm_summary(records, arm, "resistance"),
        }
        summaries[arm]["combined_exact_price_set_bundle_count"] = sum(
            1
            for record in records
            if record["arms"][arm]["support"]["exact_price_set"]
            and record["arms"][arm]["resistance"]["exact_price_set"]
        )

    def score(arm: str):
        s = summaries[arm]
        return (
            s["combined_exact_price_set_bundle_count"],
            s["support"]["exact_price_set_bundle_count"]
            + s["resistance"]["exact_price_set_bundle_count"],
            s["support"]["frozen_exact_price_match_count"]
            + s["resistance"]["frozen_exact_price_match_count"],
        )

    ranked = sorted(ARMS, key=score, reverse=True)
    winner = ranked[0]
    native_score = score("NATIVE_FIRST_ASCENDING")
    winner_score = score(winner)

    improvement = {
        "winner": winner,
        "winner_score": winner_score,
        "native_score": native_score,
        "combined_exact_bundle_gain_vs_native":
            summaries[winner]["combined_exact_price_set_bundle_count"]
            - summaries["NATIVE_FIRST_ASCENDING"]["combined_exact_price_set_bundle_count"],
        "support_exact_bundle_gain_vs_native":
            summaries[winner]["support"]["exact_price_set_bundle_count"]
            - summaries["NATIVE_FIRST_ASCENDING"]["support"]["exact_price_set_bundle_count"],
        "resistance_exact_bundle_gain_vs_native":
            summaries[winner]["resistance"]["exact_price_set_bundle_count"]
            - summaries["NATIVE_FIRST_ASCENDING"]["resistance"]["exact_price_set_bundle_count"],
    }

    if winner == "NATIVE_FIRST_ASCENDING":
        conclusion = "NO_ALTERNATIVE_CLUSTER_REPRESENTATIVE_RULE_OUTPERFORMS_NATIVE"
        next_step = "BUILD_M77_19_6_5_2_12_RAW_SUPPORT_RESISTANCE_CANDIDATE_GENERATION_FORENSICS"
    elif improvement["combined_exact_bundle_gain_vs_native"] > 0:
        conclusion = f"CLUSTER_REPRESENTATIVE_SEMANTICS_CAUSALLY_SUPPORTED_{winner}"
        next_step = "BUILD_M77_19_6_5_2_12_WINNING_LEVEL_REPRESENTATIVE_DOWNSTREAM_CAUSAL_REPLAY"
    else:
        conclusion = f"PRICE_MATCH_IMPROVEMENT_WITHOUT_FULL_BUNDLE_CLOSURE_{winner}"
        next_step = "BUILD_M77_19_6_5_2_12_RAW_SUPPORT_RESISTANCE_CANDIDATE_GENERATION_FORENSICS"

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_10_report": {
                "path": str(report5210_path),
                "sha256": EXPECTED_REPORT_5210_SHA256,
            },
            "m77_19_6_5_2_10_runner": {
                "path": str(runner5210_path),
                "sha256": EXPECTED_RUNNER_5210_SHA256,
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
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_support_resistance_candidate_generation_unmodified": True,
            "native_downstream_recompute_performed": False,
            "frozen_levels_used_only_as_scoring_authority": True,
            "predeclared_arms": list(ARMS),
            "merge_threshold": MERGE_THRESHOLD,
            "merge_threshold_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "authority_5210": authority5210,
        "monthly_bundle_count": len(records),
        "arm_summaries": summaries,
        "ranking": ranked,
        "winner_analysis": improvement,
        "records": records,
        "forensic_conclusion": conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.11 LEVEL SELECTION HYPOTHESIS CAUSAL REPLAY ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("authority_5210:", authority5210)
    print("monthly_bundle_count:", len(records))
    print("merge_threshold:", MERGE_THRESHOLD)
    print("predeclared_arms:", list(ARMS))
    for arm in ARMS:
        print(arm, summaries[arm])
    print("ranking:", ranked)
    print("winner_analysis:", improvement)
    print("forensic_conclusion:", conclusion)
    print("native_downstream_recompute_performed: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
