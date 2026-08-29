#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

VERSION = "M77.19.6.5.2.8-STRUCTURE-AND-LEVEL-GENERATION-UPSTREAM-CAUSAL-FORENSICS-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

REPORT_525_REL = "reports/m77_19_6_5_2_5_monthly_component_causal_replay_certification.json"
EXPECTED_525_SHA256 = "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"

REPORT_527_REL = "reports/m77_19_6_5_2_7_native_timeframe_state_and_participation_causal_intervention_replay.json"
EXPECTED_527_SHA256 = "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e"

PARITY_TOLERANCE = 1e-9

WEEKLY_PATHS = (
    "timeframe_states.1w.confidence",
    "timeframe_states.1w.evidence.ema50",
)
PARTICIPATION_PATHS = (
    "participation.evidence.adl",
    "participation.evidence.obv_normalized",
    "participation.evidence.up_down_volume_ratio",
    "participation.score",
    "participation.state",
    "participation.conviction",
    "participation.deterioration_risk",
)

STRUCTURE_PREFIXES = (
    "structure",
    "structure_zones",
    "breakout",
)
LEVEL_PREFIXES = (
    "support_levels",
    "resistance_levels",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_sha(root: Path, rel: str, expected: str) -> tuple[Path, Any]:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"FAIL CLOSED: required authority missing: {rel}")
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"FAIL CLOSED: authority SHA drift for {rel}: {actual}")
    return path, load_json(path)


def canonical_dist(d: dict[Any, Any] | None) -> dict[str, Any]:
    if not d:
        return {}
    def key(v: Any) -> str:
        try:
            f = float(v)
            if abs(f) < 5e-15:
                f = 0.0
            return str(round(f, 2))
        except Exception:
            return str(v)
    return {key(k): v for k, v in sorted(d.items(), key=lambda kv: float(kv[0]))}


def validate_527_against_525(r525: dict[str, Any], r527: dict[str, Any]) -> dict[str, Any]:
    b525 = (r525.get("arm_summaries") or {}).get("BASELINE") or {}
    b527 = (r527.get("arm_summaries") or {}).get("BASELINE") or {}

    checks = {
        "count": b527.get("count") == b525.get("count") == 48,
        "direction_match_pct": b527.get("direction_match_pct") == b525.get("direction_match_pct") == 100.0,
        "profile_confidence_exact_count": b527.get("profile_confidence_exact_count") == b525.get("profile_confidence_exact_count") == 0,
        "overall_score_exact_count": b527.get("overall_score_exact_count") == b525.get("overall_score_exact_count") == 2,
        "state_hash_exact_count": b527.get("state_hash_exact_count") == b525.get("state_hash_exact_count") == 0,
        "max_profile_confidence_abs_error": abs(float(b527.get("max_profile_confidence_abs_error")) - float(b525.get("max_profile_confidence_abs_error"))) <= PARITY_TOLERANCE,
        "max_score_abs_error": abs(float(b527.get("max_score_abs_error")) - float(b525.get("max_score_abs_error"))) <= PARITY_TOLERANCE,
        "score_distribution_after_key_normalization": canonical_dist(b527.get("score_signed_error_distribution_2dp")) == canonical_dist(b525.get("score_signed_error_distribution_2dp")),
        "confidence_distribution_after_key_normalization": canonical_dist(b527.get("confidence_signed_error_distribution_2dp")) == canonical_dist(b525.get("confidence_signed_error_distribution_2dp")),
    }
    checks["baseline_reproduced_after_key_normalization"] = all(checks.values())

    if not checks["baseline_reproduced_after_key_normalization"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.7 baseline does not reproduce .5 after key normalization: {checks}")

    findings = r527.get("causal_findings") or {}
    if findings.get("full_score_parity_after_combined_repair") is not True:
        raise SystemExit("FAIL CLOSED: .7 did not close score parity")
    if findings.get("full_state_parity_after_combined_repair") is not False:
        raise SystemExit("FAIL CLOSED: .7 state parity status drift")
    if r527.get("controlled_exact_input_parity_certified") is not False:
        raise SystemExit("FAIL CLOSED: .7 unexpectedly certified parity")
    if r527.get("full_23_year_reconstruction_authorized") is not False:
        raise SystemExit("FAIL CLOSED: .7 reconstruction authorization drift")
    if r527.get("production_authority_effect") is not False:
        raise SystemExit("FAIL CLOSED: .7 production authority effect drift")

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


def import_native(root: Path):
    path = root / NATIVE_RUNNER_REL
    if not path.exists():
        raise SystemExit("FAIL CLOSED: native runner missing")
    actual = sha256_file(path)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec = importlib.util.spec_from_file_location("m77_native_528", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("call_profile", "compare_profile", "StockIntelligenceService"):
        if not hasattr(module, name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    return module


def normalize_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in bundle["price_history"]:
        low = {str(k).lower(): v for k, v in raw.items()}
        date_value = low.get("date") or low.get("session_date") or low.get("price_date") or low.get("bar_date") or low.get("as_of")
        if date_value is None:
            continue
        if isinstance(date_value, dt.datetime):
            date_value = date_value.date()
        elif not isinstance(date_value, dt.date):
            date_value = dt.date.fromisoformat(str(date_value)[:10])

        def number(name: str):
            value = low.get(name)
            if value in (None, ""):
                return None
            return float(value)

        row = {
            "date": date_value,
            "open": number("open"),
            "high": number("high"),
            "low": number("low"),
            "close": number("close"),
            "volume": number("volume"),
        }
        if row["close"] is not None:
            rows.append(row)
    rows.sort(key=lambda x: x["date"])
    if not rows:
        raise RuntimeError("no normalized price history")
    return rows


def get_member(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def set_member(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = copy.deepcopy(value)
    else:
        setattr(obj, key, copy.deepcopy(value))


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, (list, tuple)) and part.isdigit():
            cur = cur[int(part)]
        else:
            cur = get_member(cur, part)
    return cur


def set_path(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            cur = get_member(cur, part)
    leaf = parts[-1]
    if isinstance(cur, list) and leaf.isdigit():
        cur[int(leaf)] = copy.deepcopy(value)
    else:
        set_member(cur, leaf, value)


def patch_mt(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.mt.analyze

    def wrapped(data_by_timeframe):
        result = original(data_by_timeframe)
        states = result.get("states")
        if not isinstance(states, dict) or "1w" not in states:
            raise RuntimeError("MT output missing 1w")
        fw = frozen_profile["timeframe_states"]["1w"]
        set_path(states["1w"], "confidence", fw["confidence"])
        set_path(states["1w"], "evidence.ema50", fw["evidence"]["ema50"])
        confs = [float(get_path(v, "confidence")) for v in states.values()]
        result["confidence"] = round(sum(confs) / len(confs), 2)
        return result

    service.mt.analyze = wrapped
    return lambda: setattr(service.mt, "analyze", original)


def patch_participation(service: Any, frozen_profile: dict[str, Any]) -> Callable[[], None]:
    original = service.part.analyze
    frozen = frozen_profile["participation"]

    def wrapped(primary):
        result = original(primary)
        for full in PARTICIPATION_PATHS:
            suffix = full.removeprefix("participation.")
            set_path(result, suffix, get_path(frozen, suffix))
        return result

    service.part.analyze = wrapped
    return lambda: setattr(service.part, "analyze", original)


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    elif hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump()
    elif hasattr(value, "dict") and callable(value.dict):
        try:
            value = value.dict()
        except Exception:
            pass
    elif not isinstance(value, (dict, list, tuple, str, int, float, bool, type(None), dt.date, dt.datetime)):
        if hasattr(value, "__dict__"):
            value = vars(value)

    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, float):
        if value == 0:
            return 0.0
        return value
    return value


def values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= PARITY_TOLERANCE
    return a == b


def path_class(path: str) -> str:
    root = path.split(".", 1)[0].replace("[]", "")
    if root in STRUCTURE_PREFIXES:
        return "STRUCTURE"
    if root in LEVEL_PREFIXES:
        return "LEVELS"
    if root == "timeframe_states":
        return "TIMEFRAME_STATE"
    if root == "participation":
        return "PARTICIPATION"
    if root in ("management", "trade_plan", "entry", "stop", "targets", "trailing"):
        return "MANAGEMENT"
    if root in ("momentum",):
        return "MOMENTUM"
    if root in ("decision_intelligence", "decision", "scores"):
        return "DECISION"
    return "OTHER"


def stable_item_key(value: Any) -> str:
    if isinstance(value, dict):
        for keys in (
            ("level_type", "price"),
            ("zone_type", "lower_bound", "upper_bound"),
            ("name",),
            ("timeframe",),
        ):
            if all(k in value for k in keys):
                return json.dumps([value[k] for k in keys], sort_keys=True, default=str)
    return json.dumps(value, sort_keys=True, default=str)


def align_lists(a: list[Any], b: list[Any]) -> tuple[list[Any], list[Any]]:
    # Where objects expose semantic identities, align by those identities before
    # recursive diffing. Otherwise preserve native order.
    if a and b and all(isinstance(v, dict) for v in a + b):
        ak = [stable_item_key(v) for v in a]
        bk = [stable_item_key(v) for v in b]
        if len(set(ak)) == len(ak) and len(set(bk)) == len(bk):
            keys = sorted(set(ak) | set(bk))
            am = dict(zip(ak, a))
            bm = dict(zip(bk, b))
            return [am.get(k, _MISSING) for k in keys], [bm.get(k, _MISSING) for k in keys]
    n = max(len(a), len(b))
    return [a[i] if i < len(a) else _MISSING for i in range(n)], [b[i] if i < len(b) else _MISSING for i in range(n)]


class _Missing:
    pass
_MISSING = _Missing()


def recursive_diff(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if a is _MISSING or b is _MISSING:
        diffs.append({
            "path": path,
            "kind": "MISSING_SIDE",
            "isolated": None if a is _MISSING else a,
            "frozen": None if b is _MISSING else b,
        })
        return diffs

    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            child = f"{path}.{key}" if path else key
            diffs.extend(recursive_diff(a.get(key, _MISSING), b.get(key, _MISSING), child))
        return diffs

    if isinstance(a, list) and isinstance(b, list):
        aa, bb = align_lists(a, b)
        for av, bv in zip(aa, bb):
            child = f"{path}[]" if path else "[]"
            diffs.extend(recursive_diff(av, bv, child))
        return diffs

    if type(a) != type(b) and not (
        isinstance(a, (int, float)) and isinstance(b, (int, float))
    ):
        diffs.append({"path": path, "kind": "TYPE", "isolated": a, "frozen": b})
        return diffs

    if not values_equal(a, b):
        item = {"path": path, "kind": "VALUE", "isolated": a, "frozen": b}
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            item["abs_error"] = abs(float(a) - float(b))
            item["signed_error"] = float(a) - float(b)
        diffs.append(item)
    return diffs


def compare_profile_source_forensics(native) -> dict[str, Any]:
    src = inspect.getsource(native.compare_profile)
    source_lines = src.splitlines()
    return {
        "source_available": True,
        "line_count": len(source_lines),
        "mentions_state_hash": "state_hash" in src,
        "mentions_overall_score": "overall_score" in src,
        "mentions_confidence": "confidence" in src,
        "mentions_json": "json" in src,
        "mentions_sha": "sha" in src.lower() or "hashlib" in src,
        "source_sha256": hashlib.sha256(src.encode()).hexdigest(),
        "source_excerpt": source_lines[:80],
    }


def run_combined(native, symbol, rows, as_of, sessions, frozen_output, frozen_profile):
    service = native.StockIntelligenceService()
    restore_mt = patch_mt(service, frozen_profile)
    restore_part = patch_participation(service, frozen_profile)
    try:
        profile = native.call_profile(service, symbol, rows, as_of, sessions, 300, 750)
    finally:
        restore_part()
        restore_mt()

    if profile is None:
        raise RuntimeError(f"combined profile ineligible for {symbol}")

    comparison = native.compare_profile(profile, frozen_output)
    return profile, comparison


def aggregate_diff_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}

    for record in records:
        seen_paths = set()
        for d in record["residual_differences"]:
            path = d["path"]
            if path not in agg:
                agg[path] = {
                    "path": path,
                    "domain": path_class(path),
                    "bundle_occurrences": 0,
                    "difference_count": 0,
                    "kinds": Counter(),
                    "max_abs_error": 0.0,
                    "examples": [],
                }
            x = agg[path]
            x["difference_count"] += 1
            x["kinds"][d["kind"]] += 1
            if "abs_error" in d:
                x["max_abs_error"] = max(x["max_abs_error"], float(d["abs_error"]))
            if len(x["examples"]) < 3:
                x["examples"].append({
                    "symbol": record["symbol"],
                    "as_of": record["as_of"],
                    "isolated": d.get("isolated"),
                    "frozen": d.get("frozen"),
                    "kind": d["kind"],
                })
            if path not in seen_paths:
                x["bundle_occurrences"] += 1
                seen_paths.add(path)

    out = []
    for x in agg.values():
        x = dict(x)
        x["kinds"] = dict(x["kinds"])
        out.append(x)

    out.sort(key=lambda x: (
        0 if x["domain"] in ("STRUCTURE", "LEVELS") else 1,
        -x["bundle_occurrences"],
        -x["difference_count"],
        x["path"],
    ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_8_structure_and_level_generation_upstream_causal_forensics.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    p525, r525 = require_sha(root, REPORT_525_REL, EXPECTED_525_SHA256)
    p527, r527 = require_sha(root, REPORT_527_REL, EXPECTED_527_SHA256)
    baseline_authority_validation = validate_527_against_525(r525, r527)

    native = import_native(root)
    source_forensics = compare_profile_source_forensics(native)
    sessions = load_spy_sessions()

    monthly_files = sorted((root / args.bundle_root / "monthly").glob("*.json"))
    if len(monthly_files) != 48:
        raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}")

    records = []
    for file_path in monthly_files:
        bundle = load_json(file_path)
        frozen_profile = bundle["frozen_profile"]
        frozen_output = bundle["frozen_output"]
        identity = bundle["prediction_identity"]
        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(str(identity["as_of"])[:10])
        rows = normalize_rows(bundle)

        profile, comparison = run_combined(
            native, symbol, rows, as_of, sessions, frozen_output, frozen_profile
        )

        if float(comparison["confidence_abs_error"]) > PARITY_TOLERANCE:
            raise SystemExit(f"FAIL CLOSED: combined confidence closure regressed for {symbol}")
        if float(comparison["score_abs_error"]) > PARITY_TOLERANCE:
            raise SystemExit(f"FAIL CLOSED: combined score closure regressed for {symbol}")
        if bool(comparison["state_hash_match"]):
            raise SystemExit(
                f"FAIL CLOSED: state hash unexpectedly matched before structure/level forensics for {symbol}"
            )

        isolated_dict = jsonable(profile)
        frozen_dict = jsonable(frozen_profile)
        diffs = recursive_diff(isolated_dict, frozen_dict)

        # Weekly + participation are already causally closed. Remove those exact
        # intervention paths from residual-path ranking so the report focuses on
        # the still-unexplained state payload.
        closed_roots = set(WEEKLY_PATHS) | set(PARTICIPATION_PATHS)
        residual = [
            d for d in diffs
            if not any(d["path"] == p or d["path"].startswith(p + ".") for p in closed_roots)
        ]

        records.append({
            "bundle": str(file_path.relative_to(root)),
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "combined_confidence_abs_error": float(comparison["confidence_abs_error"]),
            "combined_score_abs_error": float(comparison["score_abs_error"]),
            "state_hash_match": bool(comparison["state_hash_match"]),
            "residual_difference_count": len(residual),
            "residual_domain_counts": dict(Counter(path_class(d["path"]) for d in residual)),
            "residual_differences": residual,
        })

    path_inventory = aggregate_diff_stats(records)
    domain_counts = Counter()
    domain_bundle_hits = Counter()
    for item in path_inventory:
        domain_counts[item["domain"]] += item["difference_count"]
        domain_bundle_hits[item["domain"]] += item["bundle_occurrences"]

    structure_level = [
        x for x in path_inventory if x["domain"] in ("STRUCTURE", "LEVELS")
    ]
    structure_level_paths_all_48 = [
        x["path"] for x in structure_level if x["bundle_occurrences"] == 48
    ]

    state_hash_zero_48 = sum(r["state_hash_match"] for r in records) == 0
    score_closed_48 = sum(r["combined_score_abs_error"] <= PARITY_TOLERANCE for r in records) == 48
    confidence_closed_48 = sum(r["combined_confidence_abs_error"] <= PARITY_TOLERANCE for r in records) == 48

    if structure_level:
        forensic_conclusion = (
            "SCORE_AND_CONFIDENCE_CAUSALLY_CLOSED; RESIDUAL_STATE_DIVERGENCE_INVENTORIED_WITH_STRUCTURE_LEVEL_PATHS_PRESENT"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_9_STRUCTURE_LEVEL_MINIMAL_CAUSAL_INTERVENTION_REPLAY"
        )
    else:
        forensic_conclusion = (
            "SCORE_AND_CONFIDENCE_CAUSALLY_CLOSED; NO_STRUCTURE_LEVEL_RESIDUAL_PATHS_FOUND_IN_FULL_PROFILE_DIFF"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_9_STATE_HASH_PROJECTION_SPECIFIC_FORENSICS"
        )

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_5": {"path": str(p525), "sha256": EXPECTED_525_SHA256},
            "m77_19_6_5_2_7": {"path": str(p527), "sha256": EXPECTED_527_SHA256},
            "native_runner": {
                "path": str(root / NATIVE_RUNNER_REL),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
        },
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "closed_weekly_and_participation_repairs_are_forensic_controls_only": True,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "baseline_authority_validation": baseline_authority_validation,
        "baseline_reproduced_false_in_527_classification": (
            "FALSE_NEGATIVE_FROM_NUMERIC_VS_JSON_STRING_DISTRIBUTION_KEYS"
        ),
        "compare_profile_source_forensics": source_forensics,
        "monthly_bundle_count": len(records),
        "combined_control": {
            "profile_confidence_exact_count": sum(
                r["combined_confidence_abs_error"] <= PARITY_TOLERANCE for r in records
            ),
            "overall_score_exact_count": sum(
                r["combined_score_abs_error"] <= PARITY_TOLERANCE for r in records
            ),
            "state_hash_exact_count": sum(r["state_hash_match"] for r in records),
            "confidence_closed_48": confidence_closed_48,
            "score_closed_48": score_closed_48,
            "state_hash_zero_48": state_hash_zero_48,
        },
        "residual_domain_difference_counts": dict(domain_counts),
        "residual_domain_bundle_hits": dict(domain_bundle_hits),
        "residual_path_count": len(path_inventory),
        "structure_level_residual_path_count": len(structure_level),
        "structure_level_paths_all_48": structure_level_paths_all_48,
        "structure_level_path_inventory": structure_level,
        "all_residual_path_inventory": path_inventory,
        "records": records,
        "forensic_conclusion": forensic_conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")

    print("=== M77.19.6.5.2.8 STRUCTURE & LEVEL GENERATION UPSTREAM CAUSAL FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("baseline_authority_validation:", baseline_authority_validation)
    print("baseline_reproduced_false_in_527_classification: FALSE_NEGATIVE_FROM_NUMERIC_VS_JSON_STRING_DISTRIBUTION_KEYS")
    print("combined_control:", report["combined_control"])
    print("residual_domain_difference_counts:", report["residual_domain_difference_counts"])
    print("residual_path_count:", report["residual_path_count"])
    print("structure_level_residual_path_count:", report["structure_level_residual_path_count"])
    print("structure_level_paths_all_48:", report["structure_level_paths_all_48"])
    print("top_structure_level_paths:", structure_level[:20])
    print("forensic_conclusion:", forensic_conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
