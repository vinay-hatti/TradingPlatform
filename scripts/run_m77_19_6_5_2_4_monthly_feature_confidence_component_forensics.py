#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.4-MONTHLY-FEATURE-CONFIDENCE-COMPONENT-FORENSICS-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_5232_REPORT_SHA256 = "3f43cc0ae88dad4f322240e419a1f3c090e178a6d835256bdee3b9437246a58b"

NUMERIC_TOLERANCE = 1e-9
ROUND_DIGITS = 12
MAX_REPORTED_PATHS = 100


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


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

    result = set()

    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        result.add(value)

    if not result:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")

    return result


def import_native(root: Path):
    path = root / NATIVE_RUNNER_REL

    if not path.exists():
        raise SystemExit("FAIL CLOSED: native runner missing")

    actual = sha256_file(path)

    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(
            f"FAIL CLOSED: native runner SHA drift: {actual}"
        )

    spec = importlib.util.spec_from_file_location(
        "m77_native_524",
        path,
    )

    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in (
        "call_profile",
        "compare_profile",
        "StockIntelligenceService",
    ):
        if not hasattr(module, name):
            raise SystemExit(
                f"FAIL CLOSED: native runner missing {name}"
            )

    return module


def require_5232(root: Path):
    path = (
        root
        / "reports"
        / "m77_19_6_5_2_3_2_native_comparator_monthly_session_cutoff_forensics.json"
    )

    if not path.exists():
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.3.2 report missing")

    actual = sha256_file(path)

    if actual != EXPECTED_5232_REPORT_SHA256:
        raise SystemExit(
            f"FAIL CLOSED: M77.19.6.5.2.3.2 report SHA drift: {actual}"
        )

    report = load_json(path)

    if report.get("forensic_conclusion") != (
        "MONTHLY_PARITY_NOT_EXPLAINED_BY_INPUT_SESSION_CUTOFF_CONTEXT"
    ):
        raise SystemExit(
            "FAIL CLOSED: M77.19.6.5.2.3.2 conclusion not authoritative"
        )

    repro = report.get(
        "repaired_nominal_authority_reproduction",
        {},
    )

    if repro.get("pass") is not True:
        raise SystemExit(
            "FAIL CLOSED: M77.19.6.5.2.3.2 nominal reproduction failed"
        )

    session = report.get(
        "session_cutoff_forensics",
        {},
    )

    if session.get("exact_candidate_count") != 0:
        raise SystemExit(
            "FAIL CLOSED: session cutoff recovered exact monthly candidates"
        )

    return path, report


def normalize_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []

    for raw in bundle["price_history"]:
        low = {
            str(key).lower(): value
            for key, value in raw.items()
        }

        date_value = (
            low.get("date")
            or low.get("session_date")
            or low.get("price_date")
            or low.get("bar_date")
            or low.get("as_of")
        )

        if date_value is None:
            continue

        if isinstance(date_value, dt.datetime):
            date_value = date_value.date()
        elif not isinstance(date_value, dt.date):
            date_value = dt.date.fromisoformat(
                str(date_value)[:10]
            )

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

    rows.sort(key=lambda item: item["date"])

    if not rows:
        raise RuntimeError("no normalized price history")

    return rows


def json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 20:
        return repr(value)

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()

    if dataclasses.is_dataclass(value):
        return {
            str(k): json_safe(v, depth + 1)
            for k, v in dataclasses.asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(k): json_safe(v, depth + 1)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            json_safe(v, depth + 1)
            for v in value
        ]

    for method_name in (
        "model_dump",
        "dict",
        "to_dict",
        "as_dict",
    ):
        method = getattr(value, method_name, None)

        if callable(method):
            try:
                converted = method()
            except TypeError:
                continue

            return json_safe(converted, depth + 1)

    if hasattr(value, "__dict__"):
        return {
            str(k): json_safe(v, depth + 1)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }

    return repr(value)


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}

    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten(child, path))
        return result

    if isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            result.update(flatten(child, path))
        return result

    result[prefix] = value
    return result


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def compare_shared_paths(
    isolated_flat: dict[str, Any],
    frozen_flat: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []

    for path in sorted(
        set(isolated_flat)
        & set(frozen_flat)
    ):
        isolated_value = isolated_flat[path]
        frozen_value = frozen_flat[path]

        isolated_number = numeric(isolated_value)
        frozen_number = numeric(frozen_value)

        if (
            isolated_number is not None
            and frozen_number is not None
        ):
            signed = isolated_number - frozen_number
            rows.append(
                {
                    "path": path,
                    "kind": "numeric",
                    "isolated": isolated_number,
                    "frozen": frozen_number,
                    "signed_error": signed,
                    "abs_error": abs(signed),
                    "match": abs(signed) <= NUMERIC_TOLERANCE,
                }
            )
            continue

        match = isolated_value == frozen_value

        rows.append(
            {
                "path": path,
                "kind": "scalar",
                "isolated": isolated_value,
                "frozen": frozen_value,
                "match": match,
            }
        )

    return rows


def find_value_paths(
    flat: dict[str, Any],
    target: float,
    tolerance: float = 1e-9,
) -> list[str]:
    matches = []

    for path, value in flat.items():
        number = numeric(value)

        if (
            number is not None
            and abs(number - target) <= tolerance
        ):
            matches.append(path)

    return sorted(matches)


def source_fragments(native) -> dict[str, str]:
    fragments = {}

    for name in (
        "call_profile",
        "compare_profile",
    ):
        try:
            fragments[name] = inspect.getsource(
                getattr(native, name)
            )
        except Exception as exc:
            fragments[name] = (
                f"<source unavailable: {type(exc).__name__}: {exc}>"
            )

    try:
        service_cls = native.StockIntelligenceService
        fragments["StockIntelligenceService"] = inspect.getsource(
            service_cls
        )
    except Exception as exc:
        fragments["StockIntelligenceService"] = (
            f"<source unavailable: {type(exc).__name__}: {exc}>"
        )

    return fragments


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        default=".",
    )

    parser.add_argument(
        "--bundle-root",
        default=(
            "research_data/m77_19_6_4_2/"
            "exact_frozen_input_context_bundles"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/"
            "m77_19_6_5_2_4_"
            "monthly_feature_confidence_component_forensics.json"
        ),
    )

    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    source_5232, report_5232 = require_5232(root)
    native = import_native(root)
    session_set = load_spy_sessions()
    service = native.StockIntelligenceService()

    monthly_files = sorted(
        (
            root
            / args.bundle_root
            / "monthly"
        ).glob("*.json")
    )

    if len(monthly_files) != 48:
        raise SystemExit(
            f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}"
        )

    records = []
    path_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "observations": 0,
            "numeric_observations": 0,
            "mismatch_count": 0,
            "numeric_mismatch_count": 0,
            "signed_errors": [],
            "abs_errors": [],
        }
    )

    confidence_error_distribution = Counter()
    score_error_distribution = Counter()

    for file_path in monthly_files:
        bundle = load_json(file_path)

        if "frozen_profile" not in bundle:
            raise SystemExit(
                f"FAIL CLOSED: frozen_profile missing from {file_path.name}"
            )

        identity = bundle["prediction_identity"]
        frozen_output = bundle["frozen_output"]
        frozen_profile = bundle["frozen_profile"]

        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(
            str(identity["as_of"])[:10]
        )

        rows = normalize_rows(bundle)

        profile = native.call_profile(
            service,
            symbol,
            rows,
            as_of,
            session_set,
            300,
            750,
        )

        if profile is None:
            raise SystemExit(
                f"FAIL CLOSED: nominal native profile not eligible for {symbol}"
            )

        comparison = native.compare_profile(
            profile,
            frozen_output,
        )

        isolated_profile = json_safe(profile)
        frozen_profile_safe = json_safe(
            frozen_profile
        )

        isolated_flat = flatten(isolated_profile)
        frozen_flat = flatten(
            frozen_profile_safe
        )

        shared = compare_shared_paths(
            isolated_flat,
            frozen_flat,
        )

        for item in shared:
            stats = path_stats[item["path"]]
            stats["observations"] += 1

            if item["kind"] == "numeric":
                stats["numeric_observations"] += 1
                stats["signed_errors"].append(
                    item["signed_error"]
                )
                stats["abs_errors"].append(
                    item["abs_error"]
                )

            if not item["match"]:
                stats["mismatch_count"] += 1

                if item["kind"] == "numeric":
                    stats["numeric_mismatch_count"] += 1

        score_signed_error = (
            float(
                comparison["isolated"]["overall_score"]
            )
            - float(
                comparison["stored"]["overall_score"]
            )
        )

        confidence_signed_error = (
            float(
                comparison["isolated"]["confidence"]
            )
            - float(
                comparison["stored"]["confidence"]
            )
        )

        score_error_distribution[
            round(score_signed_error, 2)
        ] += 1

        confidence_error_distribution[
            round(confidence_signed_error, 2)
        ] += 1

        isolated_score_paths = find_value_paths(
            isolated_flat,
            float(
                comparison["isolated"]["overall_score"]
            ),
        )

        frozen_score_paths = find_value_paths(
            frozen_flat,
            float(
                comparison["stored"]["overall_score"]
            ),
        )

        isolated_confidence_paths = find_value_paths(
            isolated_flat,
            float(
                comparison["isolated"]["confidence"]
            ),
        )

        frozen_confidence_paths = find_value_paths(
            frozen_flat,
            float(
                comparison["stored"]["confidence"]
            ),
        )

        numeric_mismatches = [
            item
            for item in shared
            if (
                item["kind"] == "numeric"
                and not item["match"]
            )
        ]

        numeric_mismatches.sort(
            key=lambda item: (
                -item["abs_error"],
                item["path"],
            )
        )

        scalar_mismatches = [
            item
            for item in shared
            if (
                item["kind"] == "scalar"
                and not item["match"]
            )
        ]

        records.append(
            {
                "bundle": str(
                    file_path.relative_to(root)
                ),
                "symbol": symbol,
                "as_of": as_of.isoformat(),
                "comparison": {
                    "direction_match": bool(
                        comparison["direction_match"]
                    ),
                    "score_signed_error": score_signed_error,
                    "score_abs_error": float(
                        comparison["score_abs_error"]
                    ),
                    "confidence_signed_error": confidence_signed_error,
                    "confidence_abs_error": float(
                        comparison["confidence_abs_error"]
                    ),
                    "state_hash_match": bool(
                        comparison["state_hash_match"]
                    ),
                },
                "profile_path_counts": {
                    "isolated_leaf_paths": len(
                        isolated_flat
                    ),
                    "frozen_leaf_paths": len(
                        frozen_flat
                    ),
                    "shared_leaf_paths": len(
                        set(isolated_flat)
                        & set(frozen_flat)
                    ),
                },
                "exact_value_path_evidence": {
                    "isolated_overall_score_paths": isolated_score_paths,
                    "frozen_overall_score_paths": frozen_score_paths,
                    "isolated_confidence_paths": isolated_confidence_paths,
                    "frozen_confidence_paths": frozen_confidence_paths,
                },
                "top_numeric_component_mismatches": numeric_mismatches[:40],
                "scalar_component_mismatch_count": len(
                    scalar_mismatches
                ),
                "top_scalar_component_mismatches": scalar_mismatches[:20],
            }
        )

    aggregate_paths = []

    for path, stats in path_stats.items():
        signed = stats["signed_errors"]
        absolute = stats["abs_errors"]

        aggregate_paths.append(
            {
                "path": path,
                "observations": stats["observations"],
                "mismatch_count": stats["mismatch_count"],
                "mismatch_pct": (
                    100.0
                    * stats["mismatch_count"]
                    / stats["observations"]
                    if stats["observations"]
                    else 0.0
                ),
                "numeric_observations": stats["numeric_observations"],
                "numeric_mismatch_count": stats["numeric_mismatch_count"],
                "unique_signed_errors": (
                    sorted(
                        set(
                            round(
                                value,
                                ROUND_DIGITS,
                            )
                            for value in signed
                        )
                    )
                    if signed
                    else []
                ),
                "mean_signed_error": (
                    sum(signed) / len(signed)
                    if signed
                    else None
                ),
                "max_abs_error": (
                    max(absolute)
                    if absolute
                    else None
                ),
            }
        )

    aggregate_paths.sort(
        key=lambda item: (
            -item["mismatch_count"],
            -(
                item["max_abs_error"]
                if item["max_abs_error"] is not None
                else -1.0
            ),
            item["path"],
        )
    )

    constant_numeric_deltas = [
        item
        for item in aggregate_paths
        if (
            item["numeric_observations"] == 48
            and item["numeric_mismatch_count"] == 48
            and len(item["unique_signed_errors"]) == 1
        )
    ]

    recurring_numeric_deltas = [
        item
        for item in aggregate_paths
        if (
            item["numeric_mismatch_count"] >= 24
        )
    ]

    confidence_delta = -0.24

    confidence_candidate_paths = [
        item
        for item in constant_numeric_deltas
        if (
            item["unique_signed_errors"]
            and abs(
                item["unique_signed_errors"][0]
                - confidence_delta
            )
            <= NUMERIC_TOLERANCE
        )
    ]

    score_exact_path_frequency = Counter()

    for record in records:
        for path in record[
            "exact_value_path_evidence"
        ]["isolated_overall_score_paths"]:
            score_exact_path_frequency[
                f"isolated:{path}"
            ] += 1

        for path in record[
            "exact_value_path_evidence"
        ]["frozen_overall_score_paths"]:
            score_exact_path_frequency[
                f"frozen:{path}"
            ] += 1

    confidence_exact_path_frequency = Counter()

    for record in records:
        for path in record[
            "exact_value_path_evidence"
        ]["isolated_confidence_paths"]:
            confidence_exact_path_frequency[
                f"isolated:{path}"
            ] += 1

        for path in record[
            "exact_value_path_evidence"
        ]["frozen_confidence_paths"]:
            confidence_exact_path_frequency[
                f"frozen:{path}"
            ] += 1

    if confidence_candidate_paths:
        forensic_conclusion = (
            "MONTHLY_CONFIDENCE_DIVERGENCE_MAPPED_TO_"
            "CONSTANT_COMPONENT_PATH_DELTA"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_5_"
            "MONTHLY_COMPONENT_CAUSAL_REPLAY_CERTIFICATION"
        )
    elif constant_numeric_deltas:
        forensic_conclusion = (
            "MONTHLY_COMPONENT_DIVERGENCE_IDENTIFIED_"
            "BUT_CONFIDENCE_DRIVER_NOT_UNIQUELY_MAPPED"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_4_1_"
            "MONTHLY_CONFIDENCE_FORMULA_SOURCE_FORENSICS"
        )
    else:
        forensic_conclusion = (
            "MONTHLY_COMPONENT_DIVERGENCE_NOT_YET_"
            "LOCALIZED_TO_SHARED_FROZEN_PROFILE_PATHS"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_4_1_"
            "MONTHLY_CONFIDENCE_FORMULA_SOURCE_FORENSICS"
        )

    report = {
        "version": VERSION,
        "source_5232_report": str(
            source_5232
        ),
        "governance": {
            "research_only": True,
            "forensic_probe_only": True,
            "database_mode": (
                "READ_ONLY_SPY_SESSION_CALENDAR_ONLY"
            ),
            "production_database_writes": False,
            "native_compare_profile_is_semantic_authority": True,
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "prior_authority": {
            "monthly_bundle_count": 48,
            "direction_match_pct": 100.0,
            "max_score_abs_error": 0.23000000000000398,
            "max_confidence_abs_error": 0.2400000000000091,
            "confidence_signed_error_constant": -0.24,
            "session_cutoff_exact_candidate_count": 0,
        },
        "native_source_fragments": source_fragments(
            native
        ),
        "monthly_bundle_count": len(records),
        "score_signed_error_distribution_2dp": dict(
            sorted(
                score_error_distribution.items()
            )
        ),
        "confidence_signed_error_distribution_2dp": dict(
            sorted(
                confidence_error_distribution.items()
            )
        ),
        "aggregate_component_paths": aggregate_paths[
            :MAX_REPORTED_PATHS
        ],
        "constant_numeric_component_deltas": constant_numeric_deltas[
            :MAX_REPORTED_PATHS
        ],
        "recurring_numeric_component_deltas": recurring_numeric_deltas[
            :MAX_REPORTED_PATHS
        ],
        "confidence_minus_0_24_candidate_paths": confidence_candidate_paths[
            :MAX_REPORTED_PATHS
        ],
        "exact_score_value_path_frequency": dict(
            score_exact_path_frequency.most_common(
                50
            )
        ),
        "exact_confidence_value_path_frequency": dict(
            confidence_exact_path_frequency.most_common(
                50
            )
        ),
        "records": records,
        "forensic_conclusion": forensic_conclusion,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
    }

    output = root / args.output

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )

    print(
        "=== M77.19.6.5.2.4 MONTHLY FEATURE & CONFIDENCE COMPONENT FORENSICS ==="
    )
    print(
        "database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY"
    )
    print(
        "native_compare_profile_is_semantic_authority: True"
    )
    print(
        "monthly_bundle_count:",
        len(records),
    )
    print(
        "score_signed_error_distribution_2dp:",
        report[
            "score_signed_error_distribution_2dp"
        ],
    )
    print(
        "confidence_signed_error_distribution_2dp:",
        report[
            "confidence_signed_error_distribution_2dp"
        ],
    )
    print(
        "constant_numeric_component_delta_count:",
        len(constant_numeric_deltas),
    )
    print(
        "confidence_minus_0_24_candidate_path_count:",
        len(confidence_candidate_paths),
    )

    if confidence_candidate_paths:
        print(
            "confidence_minus_0_24_candidate_paths:",
            [
                item["path"]
                for item in confidence_candidate_paths[:20]
            ],
        )

    print(
        "forensic_conclusion:",
        forensic_conclusion,
    )
    print(
        "controlled_exact_input_parity_certified: False"
    )
    print(
        "full_23_year_reconstruction_authorized: False"
    )
    print(
        "production_authority_effect: False"
    )
    print(
        "next_step:",
        next_step,
    )
    print(
        "report:",
        output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
