#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

VERSION = "M77.19.6.5.2.3.2-NATIVE-COMPARATOR-MONTHLY-SESSION-CUTOFF-FORENSICS-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_522_REPORT_SHA256 = "704b6e70892247ed85e99d2ddc7c8a0ce2b5636c2e373c81398bd7b7755ab0d8"

NUMERIC_TOLERANCE = 1e-9
MAX_SESSION_BACKTRACK = 8


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def load_spy_sessions() -> list[dt.date]:
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

    sessions = []
    for (value,) in rows:
        if isinstance(value, dt.datetime):
            value = value.date()
        elif not isinstance(value, dt.date):
            value = dt.date.fromisoformat(str(value)[:10])
        sessions.append(value)

    sessions = sorted(set(sessions))
    if not sessions:
        raise SystemExit("FAIL CLOSED: SPY session calendar empty")

    return sessions


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
        "m77_native_5232",
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


def require_522(root: Path):
    path = (
        root
        / "reports"
        / "m77_19_6_5_2_2_native_compare_profile_parity_certification.json"
    )

    if not path.exists():
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.2 report missing")

    actual = sha256_file(path)
    if actual != EXPECTED_522_REPORT_SHA256:
        raise SystemExit(
            f"FAIL CLOSED: M77.19.6.5.2.2 report SHA drift: {actual}"
        )

    report = load_json(path)

    if report.get("controlled_exact_input_parity_certified") is not False:
        raise SystemExit(
            "FAIL CLOSED: expected failed controlled parity"
        )

    if report.get("blockers") != [
        "MONTHLY_STRICT_PARITY_NOT_CERTIFIED"
    ]:
        raise SystemExit(
            "FAIL CLOSED: expected isolated monthly blocker"
        )

    return path, report


def require_5231_failure(root: Path):
    path = (
        root
        / "reports"
        / "m77_19_6_5_2_3_1_monthly_forensic_probe_semantic_adapter_repair.json"
    )

    if path.exists():
        raise SystemExit(
            "FAIL CLOSED: unexpected completed M77.19.6.5.2.3.1 report exists; "
            "this repair is only for the observed runtime failure before report materialization"
        )

    runner_path = (
        root
        / "scripts"
        / "run_m77_19_6_5_2_3_1_monthly_forensic_probe_semantic_adapter_repair.py"
    )

    if not runner_path.exists():
        raise SystemExit(
            "FAIL CLOSED: M77.19.6.5.2.3.1 runner not installed"
        )

    text = runner_path.read_text(errors="replace")

    required_markers = (
        "certify_adapter",
        "semantic adapter field",
        "overall_score",
        "qualified_paths",
    )

    for marker in required_markers:
        if marker not in text:
            raise SystemExit(
                "FAIL CLOSED: installed M77.19.6.5.2.3.1 does not match diagnosed failed probe"
            )

    return runner_path


def normalize_rows(bundle):
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
    return rows


def candidate_sessions(
    nominal: dt.date,
    sessions: list[dt.date],
) -> list[dt.date]:
    eligible = [value for value in sessions if value <= nominal]

    return list(
        reversed(
            eligible[-(MAX_SESSION_BACKTRACK + 1):]
        )
    )


def extract_native_comparison(
    native,
    profile,
    frozen_output,
) -> dict[str, Any]:
    comparison = native.compare_profile(
        profile,
        frozen_output,
    )

    isolated = comparison["isolated"]
    stored = comparison["stored"]

    result = {
        "stored": {
            "direction": str(stored["direction"]),
            "overall_score": float(stored["overall_score"]),
            "confidence": float(stored["confidence"]),
            "state_hash": stored.get("state_hash"),
        },
        "isolated": {
            "direction": str(isolated["direction"]),
            "overall_score": float(isolated["overall_score"]),
            "confidence": float(isolated["confidence"]),
            "state_hash": isolated.get("state_hash"),
        },
        "direction_match": bool(
            comparison["direction_match"]
        ),
        "score_abs_error": float(
            comparison["score_abs_error"]
        ),
        "confidence_abs_error": float(
            comparison["confidence_abs_error"]
        ),
        "state_hash_match": bool(
            comparison["state_hash_match"]
        ),
    }

    result["score_signed_error"] = (
        result["isolated"]["overall_score"]
        - result["stored"]["overall_score"]
    )

    result["confidence_signed_error"] = (
        result["isolated"]["confidence"]
        - result["stored"]["confidence"]
    )

    return result


def exact_match(comparison: dict[str, Any]) -> bool:
    return (
        comparison["direction_match"]
        and comparison["score_abs_error"]
        <= NUMERIC_TOLERANCE
        and comparison["confidence_abs_error"]
        <= NUMERIC_TOLERANCE
    )


def find_monthly_summary(report: Any):
    if isinstance(report, dict):
        if (
            "MONTHLY" in report
            and isinstance(report["MONTHLY"], dict)
            and "max_score_abs_error" in report["MONTHLY"]
        ):
            return report["MONTHLY"]

        for value in report.values():
            found = find_monthly_summary(value)
            if found is not None:
                return found

    if isinstance(report, list):
        for value in report:
            found = find_monthly_summary(value)
            if found is not None:
                return found

    return None


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
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
            "m77_19_6_5_2_3_2_"
            "native_comparator_monthly_session_cutoff_forensics.json"
        ),
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    source_522, report_522 = require_522(root)
    failed_5231_runner = require_5231_failure(root)

    monthly_authority = find_monthly_summary(
        report_522
    )

    if monthly_authority is None:
        raise SystemExit(
            "FAIL CLOSED: MONTHLY M77.19.6.5.2.2 authority missing"
        )

    native = import_native(root)

    native_compare_source = inspect.getsource(
        native.compare_profile
    )

    session_list = load_spy_sessions()
    session_set = set(session_list)

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

    for file_path in monthly_files:
        bundle = load_json(file_path)
        identity = bundle["prediction_identity"]
        frozen = bundle["frozen_output"]

        symbol = str(identity["symbol"])
        nominal_as_of = dt.date.fromisoformat(
            str(identity["as_of"])[:10]
        )

        rows = normalize_rows(bundle)

        if not rows:
            raise SystemExit(
                f"FAIL CLOSED: no rows for {symbol}"
            )

        candidates = []

        for backtrack, cutoff in enumerate(
            candidate_sessions(
                nominal_as_of,
                session_list,
            )
        ):
            visible_rows = [
                row
                for row in rows
                if row["date"] <= cutoff
            ]

            if not visible_rows:
                continue

            try:
                # Crucial governance fix:
                # monthly evaluation date remains the certified nominal as_of.
                # Only visible input history is varied.
                profile = native.call_profile(
                    service,
                    symbol,
                    visible_rows,
                    nominal_as_of,
                    session_set,
                    300,
                    750,
                )

                if profile is None:
                    raise RuntimeError(
                        "native profile not eligible"
                    )

                comparison = extract_native_comparison(
                    native,
                    profile,
                    frozen,
                )

                candidates.append(
                    {
                        "session_backtrack": backtrack,
                        "candidate_input_cutoff": cutoff.isoformat(),
                        "evaluation_as_of": nominal_as_of.isoformat(),
                        "input_row_count": len(visible_rows),
                        "input_last_date": (
                            visible_rows[-1]["date"].isoformat()
                        ),
                        **comparison,
                        "exact_semantic_match": exact_match(
                            comparison
                        ),
                    }
                )

            except Exception as exc:
                candidates.append(
                    {
                        "session_backtrack": backtrack,
                        "candidate_input_cutoff": cutoff.isoformat(),
                        "evaluation_as_of": nominal_as_of.isoformat(),
                        "error": type(exc).__name__,
                        "message": str(exc)[:1200],
                        "exact_semantic_match": False,
                    }
                )

        valid = [
            candidate
            for candidate in candidates
            if "error" not in candidate
        ]

        baseline = next(
            (
                candidate
                for candidate in valid
                if candidate["session_backtrack"] == 0
            ),
            None,
        )

        if baseline is None:
            raise SystemExit(
                f"FAIL CLOSED: nominal baseline comparison missing for {symbol}"
            )

        best = min(
            valid,
            key=lambda candidate: (
                0
                if candidate["direction_match"]
                else 1,
                candidate["confidence_abs_error"],
                candidate["score_abs_error"],
                candidate["session_backtrack"],
            ),
        )

        records.append(
            {
                "bundle": str(
                    file_path.relative_to(root)
                ),
                "symbol": symbol,
                "nominal_as_of": nominal_as_of.isoformat(),
                "baseline": baseline,
                "best_candidate": best,
                "exact_candidate_found": any(
                    candidate["exact_semantic_match"]
                    for candidate in valid
                ),
                "candidates": candidates,
            }
        )

    baselines = [
        record["baseline"]
        for record in records
    ]

    baseline_summary = {
        "comparison_count": len(baselines),
        "direction_match_pct": (
            100.0
            * sum(
                item["direction_match"]
                for item in baselines
            )
            / len(baselines)
        ),
        "max_score_abs_error": max(
            item["score_abs_error"]
            for item in baselines
        ),
        "max_confidence_abs_error": max(
            item["confidence_abs_error"]
            for item in baselines
        ),
        "mean_score_signed_error": mean(
            item["score_signed_error"]
            for item in baselines
        ),
        "median_score_signed_error": median(
            item["score_signed_error"]
            for item in baselines
        ),
        "unique_confidence_signed_errors": sorted(
            set(
                round(
                    item["confidence_signed_error"],
                    12,
                )
                for item in baselines
            )
        ),
        "score_signed_error_distribution_2dp": dict(
            sorted(
                Counter(
                    round(
                        item["score_signed_error"],
                        2,
                    )
                    for item in baselines
                ).items()
            )
        ),
    }

    expected = {
        "direction_match_pct": float(
            monthly_authority[
                "direction_match_pct"
            ]
        ),
        "max_score_abs_error": float(
            monthly_authority[
                "max_score_abs_error"
            ]
        ),
        "max_confidence_abs_error": float(
            monthly_authority[
                "max_confidence_abs_error"
            ]
        ),
    }

    observed = {
        key: baseline_summary[key]
        for key in expected
    }

    reproduction_pass = all(
        close(
            observed[key],
            expected[key],
        )
        for key in expected
    )

    if not reproduction_pass:
        raise SystemExit(
            "FAIL CLOSED: repaired nominal baseline does not reproduce "
            f"M77.19.6.5.2.2 monthly authority: expected={expected} "
            f"observed={observed}"
        )

    exact_records = [
        record
        for record in records
        if record["exact_candidate_found"]
    ]

    best_candidates = [
        record["best_candidate"]
        for record in records
    ]

    exact_all = len(exact_records) == 48

    if exact_all:
        conclusion = (
            "MONTHLY_PARITY_ROOT_CAUSE_"
            "EXPLAINED_BY_INPUT_SESSION_CUTOFF_CONTEXT"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_4_"
            "GOVERNED_MONTHLY_CONTEXT_PARITY_CERTIFICATION"
        )

    elif exact_records:
        conclusion = (
            "MONTHLY_PARITY_PARTIALLY_EXPLAINED_"
            "BY_INPUT_SESSION_CUTOFF_CONTEXT"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_4_"
            "MONTHLY_FEATURE_CONFIDENCE_COMPONENT_FORENSICS"
        )

    else:
        conclusion = (
            "MONTHLY_PARITY_NOT_EXPLAINED_"
            "BY_INPUT_SESSION_CUTOFF_CONTEXT"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_4_"
            "MONTHLY_FEATURE_CONFIDENCE_COMPONENT_FORENSICS"
        )

    report = {
        "version": VERSION,
        "source_522_report": str(source_522),
        "superseded_failed_5231_runner": str(
            failed_5231_runner
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
        "native_compare_profile_source": (
            native_compare_source
        ),
        "diagnosis_of_m77_19_6_5_2_3_1": {
            "valid_forensic_conclusion": False,
            "reason": (
                "FAILED_SEMANTIC_ADAPTER_DISCOVERY_"
                "DESPITE_EXISTING_NATIVE_COMPARE_PROFILE_AUTHORITY"
            ),
        },
        "repaired_nominal_authority_reproduction": {
            "expected": expected,
            "observed": observed,
            "pass": reproduction_pass,
        },
        "monthly_bundle_count": len(records),
        "baseline_summary": baseline_summary,
        "records": records,
        "session_cutoff_forensics": {
            "exact_candidate_count": len(
                exact_records
            ),
            "exact_candidate_symbols": [
                record["symbol"]
                for record in exact_records
            ],
            "best_candidate_backtrack_distribution": dict(
                sorted(
                    Counter(
                        int(
                            candidate[
                                "session_backtrack"
                            ]
                        )
                        for candidate in best_candidates
                    ).items()
                )
            ),
            "all_monthly_exact_match_recovered_by_input_session_cutoff": exact_all,
        },
        "forensic_conclusion": conclusion,
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
        "=== M77.19.6.5.2.3.2 NATIVE COMPARATOR "
        "MONTHLY SESSION-CUTOFF FORENSICS ==="
    )
    print(
        "m77_19_6_5_2_3_1_conclusion_valid: False"
    )
    print(
        "native_compare_profile_is_semantic_authority: True"
    )
    print(
        "repaired_nominal_authority_reproduction:",
        report[
            "repaired_nominal_authority_reproduction"
        ],
    )
    print(
        "baseline_summary:",
        baseline_summary,
    )
    print(
        "session_cutoff_forensics:",
        report["session_cutoff_forensics"],
    )
    print(
        "forensic_conclusion:",
        conclusion,
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
