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
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.10-LEVEL-GENERATION-INPUT-AND-SELECTION-SEMANTICS-FORENSICS-1.0"

REPORT_529_REL = "reports/m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.json"
EXPECTED_529_SHA256 = "91b1c236014ea2acef7e21e849434cd91c7fd5638d9ab6f54b3d03b3687ffdcf"

RUNNER_529_REL = "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
EXPECTED_529_RUNNER_SHA256 = "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

PARITY_TOLERANCE = 1e-9
PRICE_RELATIVE_BANDS = (0.001, 0.005, 0.01)
RESEARCH_ONLY = True


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


def validate_529(report: dict[str, Any]) -> dict[str, Any]:
    findings = report.get("causal_findings") or {}
    arms = report.get("arm_summaries") or {}
    combined = arms.get("LEVELS_AND_STRUCTURE") or {}

    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == 48,
        "levels_intervention_exact_48": findings.get("levels_intervention_exact_48") is True,
        "structure_intervention_exact_48": findings.get("structure_intervention_exact_48") is True,
        "combined_levels_structure_exact_48": findings.get("combined_levels_structure_exact_48") is True,
        "combined_confidence_exact_48": combined.get("profile_confidence_exact_count") == 48,
        "combined_score_exact_48": combined.get("overall_score_exact_count") == 48,
        "combined_levels_exact_48": (
            combined.get("support_levels_exact_count") == 48
            and combined.get("resistance_levels_exact_count") == 48
        ),
        "combined_structure_exact_48": combined.get("structure_zones_exact_count") == 48,
        "combined_decision_exact_48": combined.get("decision_intelligence_exact_count") == 48,
        "combined_trade_plan_open_48": combined.get("trade_plan_exact_count") == 0,
        "combined_state_open_48": combined.get("state_hash_exact_count") == 0,
        "forensic_conclusion": report.get("forensic_conclusion") == (
            "LEVEL_GENERATION_CAUSALLY_DRIVES_STRUCTURE_DIVERGENCE_BUT_FULL_STATE_PARITY_REMAINS_OPEN"
        ),
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_authority_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.9 authority validation failed: {checks}")
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


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)[:10]


def jsonable(value: Any) -> Any:
    import dataclasses

    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    elif hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump()
    elif hasattr(value, "dict") and callable(value.dict):
        try:
            value = value.dict()
        except Exception:
            pass
    elif not isinstance(
        value,
        (dict, list, tuple, str, int, float, bool, type(None), dt.date, dt.datetime),
    ):
        if hasattr(value, "__dict__"):
            value = vars(value)

    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def level_price(item: Any) -> float | None:
    if isinstance(item, dict):
        value = item.get("price")
    else:
        value = getattr(item, "price", None)
    if value in (None, ""):
        return None
    return float(value)


def canonical_level(item: Any) -> dict[str, Any]:
    value = jsonable(item)
    if not isinstance(value, dict):
        return {"value": value}
    return value


def exact_level(a: Any, b: Any) -> bool:
    return canonical_level(a) == canonical_level(b)


def price_exact(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= PARITY_TOLERANCE


def relative_error(a: float, b: float) -> float:
    denominator = max(abs(float(b)), PARITY_TOLERANCE)
    return abs(float(a) - float(b)) / denominator


def nearest_price(target: float, candidates: list[float]) -> dict[str, Any]:
    if not candidates:
        return {
            "available": False,
            "nearest": None,
            "abs_error": None,
            "relative_error": None,
        }
    nearest = min(candidates, key=lambda x: abs(float(x) - float(target)))
    return {
        "available": True,
        "nearest": nearest,
        "abs_error": abs(float(nearest) - float(target)),
        "relative_error": relative_error(nearest, target),
    }


def price_set_relation(native_prices: list[float], frozen_prices: list[float]) -> str:
    def contains_exact(haystack: list[float], value: float) -> bool:
        return any(price_exact(x, value) for x in haystack)

    native_in_frozen = all(contains_exact(frozen_prices, x) for x in native_prices)
    frozen_in_native = all(contains_exact(native_prices, x) for x in frozen_prices)

    if native_in_frozen and frozen_in_native:
        return "EXACT_PRICE_SET"
    if native_in_frozen:
        return "NATIVE_PRICE_SUBSET_OF_FROZEN"
    if frozen_in_native:
        return "FROZEN_PRICE_SUBSET_OF_NATIVE"
    if set() == set(native_prices) == set(frozen_prices):
        return "BOTH_EMPTY"
    return "PARTIAL_OR_DISJOINT_PRICE_SET"


def compare_level_side(native_items: list[Any], frozen_items: list[Any]) -> dict[str, Any]:
    native_prices = [x for x in (level_price(v) for v in native_items) if x is not None]
    frozen_prices = [x for x in (level_price(v) for v in frozen_items) if x is not None]

    native_exact_payload_matches = sum(
        1 for n in native_items if any(exact_level(n, f) for f in frozen_items)
    )
    frozen_exact_payload_matches = sum(
        1 for f in frozen_items if any(exact_level(f, n) for n in native_items)
    )

    native_price_matches = sum(
        1 for n in native_prices if any(price_exact(n, f) for f in frozen_prices)
    )
    frozen_price_matches = sum(
        1 for f in frozen_prices if any(price_exact(f, n) for n in native_prices)
    )

    frozen_nearest = [
        {
            "frozen_price": f,
            **nearest_price(f, native_prices),
        }
        for f in frozen_prices
    ]

    native_nearest = [
        {
            "native_price": n,
            **nearest_price(n, frozen_prices),
        }
        for n in native_prices
    ]

    within_bands = {
        str(band): sum(
            1
            for item in frozen_nearest
            if item["relative_error"] is not None and item["relative_error"] <= band
        )
        for band in PRICE_RELATIVE_BANDS
    }

    return {
        "native_count": len(native_items),
        "frozen_count": len(frozen_items),
        "count_delta_native_minus_frozen": len(native_items) - len(frozen_items),
        "native_price_count": len(native_prices),
        "frozen_price_count": len(frozen_prices),
        "price_set_relation": price_set_relation(native_prices, frozen_prices),
        "native_exact_payload_match_count": native_exact_payload_matches,
        "frozen_exact_payload_match_count": frozen_exact_payload_matches,
        "native_exact_price_match_count": native_price_matches,
        "frozen_exact_price_match_count": frozen_price_matches,
        "frozen_nearest_native": frozen_nearest,
        "native_nearest_frozen": native_nearest,
        "frozen_nearest_within_relative_bands": within_bands,
        "native_level_field_inventory": sorted(
            set().union(
                *[
                    set(canonical_level(item).keys())
                    for item in native_items
                    if isinstance(canonical_level(item), dict)
                ]
            )
            if native_items
            else set()
        ),
        "frozen_level_field_inventory": sorted(
            set().union(
                *[
                    set(canonical_level(item).keys())
                    for item in frozen_items
                    if isinstance(canonical_level(item), dict)
                ]
            )
            if frozen_items
            else set()
        ),
    }


def summarize_timeframe_input(data_by_timeframe: Any) -> dict[str, Any]:
    if not isinstance(data_by_timeframe, dict):
        return {
            "type": f"{type(data_by_timeframe).__module__}.{type(data_by_timeframe).__qualname__}",
            "timeframes": {},
        }

    result = {}
    for timeframe, rows in data_by_timeframe.items():
        try:
            sequence = list(rows)
        except Exception:
            result[str(timeframe)] = {
                "row_count": None,
                "first_date": None,
                "last_date": None,
                "row_type": f"{type(rows).__module__}.{type(rows).__qualname__}",
            }
            continue

        dates = []
        for row in sequence:
            if isinstance(row, dict):
                value = (
                    row.get("date")
                    or row.get("session_date")
                    or row.get("as_of")
                    or row.get("timestamp")
                )
            else:
                value = (
                    getattr(row, "date", None)
                    or getattr(row, "session_date", None)
                    or getattr(row, "as_of", None)
                    or getattr(row, "timestamp", None)
                )
            d = normalize_date(value)
            if d:
                dates.append(d)

        result[str(timeframe)] = {
            "row_count": len(sequence),
            "first_date": min(dates) if dates else None,
            "last_date": max(dates) if dates else None,
            "row_type": (
                f"{type(sequence[0]).__module__}.{type(sequence[0]).__qualname__}"
                if sequence
                else None
            ),
        }

    return {
        "type": f"{type(data_by_timeframe).__module__}.{type(data_by_timeframe).__qualname__}",
        "timeframes": result,
    }


def source_semantics(source: str) -> dict[str, Any]:
    normalized = " ".join(source.split())
    lower = normalized.lower()

    keywords = (
        "pivot",
        "rolling",
        "window",
        "support",
        "resistance",
        "dedup",
        "merge",
        "cluster",
        "strength",
        "confluence",
        "touch",
        "sort",
        "sorted",
        "reverse",
        "limit",
        "top",
        "nearest",
        "atr",
        "high",
        "low",
        "timeframe",
    )

    keyword_hits = {
        key: lower.count(key)
        for key in keywords
        if lower.count(key)
    }

    numeric_literals = []
    slices = []
    function_names = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_names.append(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                numeric_literals.append(node.value)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                slices.append(ast.unparse(node.slice))
    except Exception:
        tree = None

    return {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_line_count": len(source.splitlines()),
        "function_names": function_names,
        "keyword_hits": keyword_hits,
        "numeric_literals": numeric_literals,
        "slice_expressions": slices,
        "source": source,
    }


def capture_native_levels(service: Any):
    original = service.levels.analyze
    capture: dict[str, Any] = {}

    def wrapped(data_by_timeframe):
        capture["input"] = summarize_timeframe_input(data_by_timeframe)
        result = original(data_by_timeframe)
        capture["output"] = copy.deepcopy(result)
        return result

    service.levels.analyze = wrapped

    def restore():
        service.levels.analyze = original

    return capture, restore


def run_native_profile(native, helper529, symbol, rows, as_of, sessions):
    service = native.StockIntelligenceService()
    capture, restore = capture_native_levels(service)
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
    if "output" not in capture:
        raise RuntimeError(f"level service was not called for {symbol}")

    return profile, capture


def candidate_hypothesis(summary: dict[str, Any]) -> str:
    relations = summary["price_set_relation_distribution"]
    exact_price_pct = summary["frozen_exact_price_match_pct"]
    close_05_pct = summary["frozen_nearest_within_0_5pct_pct"]
    count_delta_nonzero_pct = summary["nonzero_count_delta_pct"]

    if exact_price_pct >= 95.0 and count_delta_nonzero_pct > 0:
        return "SELECTION_CARDINALITY_OR_DEDUPLICATION"
    if exact_price_pct >= 95.0:
        return "LEVEL_METADATA_SEMANTICS"
    if close_05_pct >= 90.0:
        return "CANDIDATE_PRICE_CALCULATION_OR_ROUNDING"
    if relations.get("NATIVE_PRICE_SUBSET_OF_FROZEN", 0) > relations.get(
        "FROZEN_PRICE_SUBSET_OF_NATIVE", 0
    ):
        return "NATIVE_SELECTION_IS_STRICTER_OR_TRUNCATED"
    if relations.get("FROZEN_PRICE_SUBSET_OF_NATIVE", 0) > relations.get(
        "NATIVE_PRICE_SUBSET_OF_FROZEN", 0
    ):
        return "FROZEN_SELECTION_IS_STRICTER_OR_TRUNCATED"
    return "INPUT_WINDOW_CANDIDATE_EXTRACTION_OR_SELECTION_SEMANTICS"


def aggregate_side(records: list[dict[str, Any]], side: str) -> dict[str, Any]:
    items = [record[side] for record in records]
    frozen_total = sum(x["frozen_price_count"] for x in items)
    frozen_exact = sum(x["frozen_exact_price_match_count"] for x in items)
    frozen_close_05 = sum(
        x["frozen_nearest_within_relative_bands"].get("0.005", 0)
        for x in items
    )

    relation_counts = Counter(x["price_set_relation"] for x in items)
    count_delta_dist = Counter(x["count_delta_native_minus_frozen"] for x in items)

    result = {
        "bundle_count": len(items),
        "native_level_total": sum(x["native_count"] for x in items),
        "frozen_level_total": sum(x["frozen_count"] for x in items),
        "frozen_exact_price_match_count": frozen_exact,
        "frozen_exact_price_match_pct": (
            100.0 * frozen_exact / frozen_total if frozen_total else 100.0
        ),
        "frozen_nearest_within_0_5pct_count": frozen_close_05,
        "frozen_nearest_within_0_5pct_pct": (
            100.0 * frozen_close_05 / frozen_total if frozen_total else 100.0
        ),
        "price_set_relation_distribution": dict(relation_counts),
        "count_delta_distribution": {
            str(key): value
            for key, value in sorted(count_delta_dist.items())
        },
        "nonzero_count_delta_bundle_count": sum(
            1 for x in items if x["count_delta_native_minus_frozen"] != 0
        ),
        "nonzero_count_delta_pct": (
            100.0
            * sum(1 for x in items if x["count_delta_native_minus_frozen"] != 0)
            / len(items)
            if items
            else 0.0
        ),
    }
    result["leading_hypothesis"] = candidate_hypothesis(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_10_level_generation_input_and_selection_semantics_forensics.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    report529_path = require_file(
        root,
        REPORT_529_REL,
        EXPECTED_529_SHA256,
        "M77.19.6.5.2.9 report",
    )
    runner529_path = require_file(
        root,
        RUNNER_529_REL,
        EXPECTED_529_RUNNER_SHA256,
        "M77.19.6.5.2.9.1 repaired runner",
    )
    native_path = require_file(
        root,
        NATIVE_RUNNER_REL,
        EXPECTED_NATIVE_RUNNER_SHA256,
        "native replay runner",
    )

    report529 = load_json(report529_path)
    authority529 = validate_529(report529)

    helper529 = import_module_from_path(runner529_path, "m77_helper_529_for_5210")
    native = import_module_from_path(native_path, "m77_native_5210")

    sessions = load_spy_sessions()

    monthly_files = sorted((root / args.bundle_root / "monthly").glob("*.json"))
    if len(monthly_files) != 48:
        raise SystemExit(
            f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}"
        )

    probe_service = native.StockIntelligenceService()
    level_service_type = type(probe_service.levels)
    level_source = inspect.getsource(level_service_type)
    semantics = source_semantics(level_source)

    records = []

    for file_path in monthly_files:
        bundle = load_json(file_path)
        identity = bundle["prediction_identity"]
        frozen_profile = bundle["frozen_profile"]

        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(str(identity["as_of"])[:10])
        rows = helper529.normalize_rows(bundle)

        profile, capture = run_native_profile(
            native,
            helper529,
            symbol,
            rows,
            as_of,
            sessions,
        )

        output = capture["output"]
        native_support = list(output.get("support_levels") or [])
        native_resistance = list(output.get("resistance_levels") or [])

        frozen_support = list(frozen_profile.get("support_levels") or [])
        frozen_resistance = list(frozen_profile.get("resistance_levels") or [])

        records.append(
            {
                "bundle": str(file_path.relative_to(root)),
                "symbol": symbol,
                "as_of": as_of.isoformat(),
                "level_input": capture["input"],
                "support": compare_level_side(native_support, frozen_support),
                "resistance": compare_level_side(
                    native_resistance,
                    frozen_resistance,
                ),
            }
        )

    support_summary = aggregate_side(records, "support")
    resistance_summary = aggregate_side(records, "resistance")

    timeframe_input_shapes = Counter()
    for record in records:
        timeframes = record["level_input"].get("timeframes") or {}
        key = tuple(
            sorted(
                (
                    timeframe,
                    info.get("row_count"),
                    info.get("first_date"),
                    info.get("last_date"),
                )
                for timeframe, info in timeframes.items()
            )
        )
        timeframe_input_shapes[str(key)] += 1

    hypotheses = Counter(
        (
            support_summary["leading_hypothesis"],
            resistance_summary["leading_hypothesis"],
        )
    )

    if (
        support_summary["leading_hypothesis"]
        == resistance_summary["leading_hypothesis"]
    ):
        forensic_conclusion = (
            "LEVEL_GENERATION_DIVERGENCE_LOCALIZED_TO_"
            + support_summary["leading_hypothesis"]
        )
    else:
        forensic_conclusion = (
            "SUPPORT_AND_RESISTANCE_LEVEL_DIVERGENCES_HAVE_DISTINCT_SELECTION_SEMANTICS"
        )

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_9": {
                "path": str(report529_path),
                "sha256": EXPECTED_529_SHA256,
            },
            "m77_19_6_5_2_9_1_runner": {
                "path": str(runner529_path),
                "sha256": EXPECTED_529_RUNNER_SHA256,
            },
            "native_runner": {
                "path": str(native_path),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
        },
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "synthetic_level_replacement_used": False,
            "native_level_service_executes_unmodified": True,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "authority_529": authority529,
        "monthly_bundle_count": len(records),
        "native_level_service": {
            "type": f"{level_service_type.__module__}.{level_service_type.__qualname__}",
            "source_semantics": semantics,
        },
        "level_input_shape_distribution": dict(timeframe_input_shapes),
        "support_summary": support_summary,
        "resistance_summary": resistance_summary,
        "records": records,
        "trade_plan_state_branch": {
            "status": "SEPARATE_DOWNSTREAM_BRANCH_REMAINS_OPEN",
            "evidence": {
                "levels_and_structure_exact_count": 48,
                "decision_intelligence_exact_count": 48,
                "trade_plan_exact_count": 0,
                "state_hash_exact_count": 0,
            },
            "action": (
                "Do not use trade-plan/state-hash mismatch as evidence against "
                "level-generation causality; investigate separately after level "
                "selection semantics are resolved."
            ),
        },
        "forensic_conclusion": forensic_conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": (
            "BUILD_M77_19_6_5_2_11_LEVEL_SELECTION_HYPOTHESIS_CAUSAL_REPLAY"
        ),
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print(
        "=== M77.19.6.5.2.10 LEVEL GENERATION INPUT & SELECTION SEMANTICS FORENSICS ==="
    )
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("synthetic_level_replacement_used: False")
    print("authority_529:", authority529)
    print("monthly_bundle_count:", len(records))
    print("native_level_service_type:", report["native_level_service"]["type"])
    print("native_level_source_semantics:", semantics)
    print("support_summary:", support_summary)
    print("resistance_summary:", resistance_summary)
    print(
        "level_input_shape_distribution:",
        report["level_input_shape_distribution"],
    )
    print(
        "trade_plan_state_branch:",
        report["trade_plan_state_branch"],
    )
    print("forensic_conclusion:", forensic_conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("report:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
