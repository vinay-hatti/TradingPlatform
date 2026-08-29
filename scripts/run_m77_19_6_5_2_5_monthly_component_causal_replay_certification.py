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
from collections import Counter
from pathlib import Path
from typing import Any, Callable

VERSION = "M77.19.6.5.2.5-MONTHLY-COMPONENT-CAUSAL-REPLAY-CERTIFICATION-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_524_REPORT_SHA256 = "9147873baa5baa3e19e528d6b47d125450316e3a32dfc595ec6064eb2093eb96"

PARITY_TOLERANCE = 1e-9
EXPECTED_WEEKLY_CONFIDENCE_DELTA = 0.5
EXPECTED_PROFILE_CONFIDENCE_DELTA = 0.24


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

    result: set[dt.date] = set()
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
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")

    spec = importlib.util.spec_from_file_location("m77_native_525", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in ("call_profile", "compare_profile", "StockIntelligenceService"):
        if not hasattr(module, name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")

    return module


def require_524(root: Path):
    path = root / "reports" / "m77_19_6_5_2_4_monthly_feature_confidence_component_forensics.json"
    if not path.exists():
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.4 report missing")

    actual = sha256_file(path)
    if actual != EXPECTED_524_REPORT_SHA256:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.4 report SHA drift: {actual}")

    report = load_json(path)

    if report.get("forensic_conclusion") != (
        "MONTHLY_CONFIDENCE_DIVERGENCE_MAPPED_TO_CONSTANT_COMPONENT_PATH_DELTA"
    ):
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.4 conclusion not authoritative")

    if report.get("monthly_bundle_count") != 48:
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.4 monthly bundle count not 48")

    candidates = {
        item.get("path"): item
        for item in report.get("constant_numeric_component_deltas", [])
    }

    weekly = candidates.get("timeframe_states.1w.confidence")
    profile = candidates.get("confidence")

    if not weekly or weekly.get("unique_signed_errors") != [-0.5]:
        raise SystemExit("FAIL CLOSED: weekly confidence delta is not authoritative -0.5")

    if not profile or profile.get("unique_signed_errors") != [-0.24]:
        raise SystemExit("FAIL CLOSED: profile confidence delta is not authoritative -0.24")

    return path, report


def normalize_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in bundle["price_history"]:
        low = {str(k).lower(): v for k, v in raw.items()}
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

    rows.sort(key=lambda item: item["date"])
    if not rows:
        raise RuntimeError("no normalized price history")
    return rows


def get_confidence(state: Any) -> float:
    if isinstance(state, dict):
        return float(state["confidence"])
    return float(getattr(state, "confidence"))


def set_confidence(state: Any, value: float) -> None:
    if isinstance(state, dict):
        state["confidence"] = float(value)
    else:
        setattr(state, "confidence", float(value))


def patch_mt_analyze(
    service: Any,
    frozen_weekly_confidence: float,
    frozen_profile_confidence: float,
    mode: str,
) -> Callable[[], None]:
    original = service.mt.analyze

    def wrapped(data_by_timeframe):
        result = original(data_by_timeframe)

        if not isinstance(result, dict):
            raise RuntimeError("MT analyze did not return dict")

        states = result.get("states")
        if not isinstance(states, dict) or "1w" not in states:
            raise RuntimeError("MT analyze missing states['1w']")

        if mode in ("WEEKLY_ONLY", "WEEKLY_AND_AGGREGATE"):
            set_confidence(states["1w"], frozen_weekly_confidence)

        if mode in ("AGGREGATE_ONLY", "WEEKLY_AND_AGGREGATE"):
            result["confidence"] = float(frozen_profile_confidence)

        return result

    service.mt.analyze = wrapped

    def restore():
        service.mt.analyze = original

    return restore


def profile_metrics(native, profile, frozen_output, frozen_profile):
    comparison = native.compare_profile(profile, frozen_output)

    weekly_state = profile.timeframe_states["1w"]
    weekly_confidence = get_confidence(weekly_state)
    frozen_weekly_confidence = float(
        frozen_profile["timeframe_states"]["1w"]["confidence"]
    )

    return {
        "direction_match": bool(comparison["direction_match"]),
        "score_signed_error": (
            float(comparison["isolated"]["overall_score"])
            - float(comparison["stored"]["overall_score"])
        ),
        "score_abs_error": float(comparison["score_abs_error"]),
        "confidence_signed_error": (
            float(comparison["isolated"]["confidence"])
            - float(comparison["stored"]["confidence"])
        ),
        "confidence_abs_error": float(comparison["confidence_abs_error"]),
        "weekly_confidence_signed_error": (
            weekly_confidence - frozen_weekly_confidence
        ),
        "weekly_confidence_abs_error": abs(
            weekly_confidence - frozen_weekly_confidence
        ),
        "state_hash_match": bool(comparison["state_hash_match"]),
        "isolated_overall_score": float(comparison["isolated"]["overall_score"]),
        "stored_overall_score": float(comparison["stored"]["overall_score"]),
        "isolated_confidence": float(comparison["isolated"]["confidence"]),
        "stored_confidence": float(comparison["stored"]["confidence"]),
        "isolated_weekly_confidence": weekly_confidence,
        "stored_weekly_confidence": frozen_weekly_confidence,
    }


def run_arm(
    native,
    symbol: str,
    rows: list[dict[str, Any]],
    as_of: dt.date,
    sessions: set[dt.date],
    frozen_output: dict[str, Any],
    frozen_profile: dict[str, Any],
    mode: str,
):
    service = native.StockIntelligenceService()

    restore = None
    if mode != "BASELINE":
        restore = patch_mt_analyze(
            service,
            float(frozen_profile["timeframe_states"]["1w"]["confidence"]),
            float(frozen_profile["confidence"]),
            mode,
        )

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
        if restore is not None:
            restore()

    if profile is None:
        raise RuntimeError(f"{mode} profile ineligible for {symbol}")

    return profile_metrics(
        native,
        profile,
        frozen_output,
        frozen_profile,
    )


def exact(value: float) -> bool:
    return abs(float(value)) <= PARITY_TOLERANCE


def summarize(records: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    values = [record["arms"][arm] for record in records]

    return {
        "count": len(values),
        "direction_match_pct": (
            100.0 * sum(v["direction_match"] for v in values) / len(values)
        ),
        "weekly_confidence_exact_count": sum(
            exact(v["weekly_confidence_signed_error"]) for v in values
        ),
        "profile_confidence_exact_count": sum(
            exact(v["confidence_signed_error"]) for v in values
        ),
        "overall_score_exact_count": sum(
            exact(v["score_signed_error"]) for v in values
        ),
        "state_hash_exact_count": sum(
            v["state_hash_match"] for v in values
        ),
        "max_weekly_confidence_abs_error": max(
            v["weekly_confidence_abs_error"] for v in values
        ),
        "max_profile_confidence_abs_error": max(
            v["confidence_abs_error"] for v in values
        ),
        "max_score_abs_error": max(
            v["score_abs_error"] for v in values
        ),
        "score_signed_error_distribution_2dp": dict(
            sorted(
                Counter(
                    round(v["score_signed_error"], 2)
                    for v in values
                ).items()
            )
        ),
        "confidence_signed_error_distribution_2dp": dict(
            sorted(
                Counter(
                    round(v["confidence_signed_error"], 2)
                    for v in values
                ).items()
            )
        ),
        "weekly_confidence_signed_error_distribution_2dp": dict(
            sorted(
                Counter(
                    round(v["weekly_confidence_signed_error"], 2)
                    for v in values
                ).items()
            )
        ),
    }


def safe_source(obj: Any) -> str:
    try:
        return inspect.getsource(obj)
    except Exception as exc:
        return f"<source unavailable: {type(exc).__name__}: {exc}>"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_5_monthly_component_causal_replay_certification.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    source_524, report_524 = require_524(root)
    native = import_native(root)
    sessions = load_spy_sessions()

    monthly_files = sorted((root / args.bundle_root / "monthly").glob("*.json"))
    if len(monthly_files) != 48:
        raise SystemExit(
            f"FAIL CLOSED: expected 48 monthly bundles, found {len(monthly_files)}"
        )

    records = []

    for file_path in monthly_files:
        bundle = load_json(file_path)
        frozen_profile = bundle["frozen_profile"]
        frozen_output = bundle["frozen_output"]
        identity = bundle["prediction_identity"]

        symbol = str(identity["symbol"])
        as_of = dt.date.fromisoformat(str(identity["as_of"])[:10])
        rows = normalize_rows(bundle)

        arms = {}
        for arm in (
            "BASELINE",
            "WEEKLY_ONLY",
            "AGGREGATE_ONLY",
            "WEEKLY_AND_AGGREGATE",
        ):
            arms[arm] = run_arm(
                native,
                symbol,
                rows,
                as_of,
                sessions,
                frozen_output,
                frozen_profile,
                arm,
            )

        records.append(
            {
                "bundle": str(file_path.relative_to(root)),
                "symbol": symbol,
                "as_of": as_of.isoformat(),
                "arms": arms,
            }
        )

    summaries = {
        arm: summarize(records, arm)
        for arm in (
            "BASELINE",
            "WEEKLY_ONLY",
            "AGGREGATE_ONLY",
            "WEEKLY_AND_AGGREGATE",
        )
    }

    baseline = summaries["BASELINE"]
    weekly = summaries["WEEKLY_ONLY"]
    aggregate = summaries["AGGREGATE_ONLY"]
    both = summaries["WEEKLY_AND_AGGREGATE"]

    baseline_reproduced = (
        baseline["weekly_confidence_signed_error_distribution_2dp"] == {-0.5: 48}
        and baseline["confidence_signed_error_distribution_2dp"] == {-0.24: 48}
        and baseline["direction_match_pct"] == 100.0
        and abs(baseline["max_score_abs_error"] - 0.23000000000000398) <= PARITY_TOLERANCE
    )

    weekly_only_does_not_recompute_profile_confidence = (
        weekly["weekly_confidence_exact_count"] == 48
        and weekly["confidence_signed_error_distribution_2dp"] == {-0.24: 48}
    )

    aggregate_intervention_restores_profile_confidence = (
        aggregate["profile_confidence_exact_count"] == 48
    )

    both_intervention_restores_weekly_and_profile_confidence = (
        both["weekly_confidence_exact_count"] == 48
        and both["profile_confidence_exact_count"] == 48
    )

    downstream_score_parity_after_confidence_repair = (
        both["overall_score_exact_count"] == 48
    )

    full_state_parity_after_confidence_repair = (
        both["state_hash_exact_count"] == 48
    )

    confidence_lineage_isolated_to_mt_aggregate_output = (
        baseline_reproduced
        and weekly_only_does_not_recompute_profile_confidence
        and aggregate_intervention_restores_profile_confidence
        and both_intervention_restores_weekly_and_profile_confidence
    )

    controlled_exact_input_parity_certified = (
        confidence_lineage_isolated_to_mt_aggregate_output
        and downstream_score_parity_after_confidence_repair
        and full_state_parity_after_confidence_repair
    )

    if controlled_exact_input_parity_certified:
        forensic_conclusion = (
            "MONTHLY_MT_CONFIDENCE_COMPONENT_CAUSALLY_EXPLAINS_FULL_PROFILE_PARITY"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_6_NATIVE_MT_CONFIDENCE_FORMULA_RECONSTRUCTION"
        )
    elif confidence_lineage_isolated_to_mt_aggregate_output:
        forensic_conclusion = (
            "MONTHLY_MT_CONFIDENCE_LINEAGE_CAUSALLY_CONFIRMED_BUT_FULL_PARITY_HAS_ADDITIONAL_UPSTREAM_DIVERGENCES"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_6_NATIVE_MT_AND_PARTICIPATION_UPSTREAM_DIVERGENCE_FORENSICS"
        )
    else:
        forensic_conclusion = (
            "MONTHLY_CONFIDENCE_CAUSAL_LINEAGE_NOT_YET_CONFIRMED"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_5_1_MT_CONFIDENCE_SOURCE_FORMULA_FORENSICS"
        )

    mt_source = safe_source(
        native.StockIntelligenceService().mt.__class__
    )

    report = {
        "version": VERSION,
        "source_524_report": str(source_524),
        "governance": {
            "research_only": True,
            "controlled_intervention_only": True,
            "database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes": False,
            "native_compare_profile_is_semantic_authority": True,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "synthetic_interventions_may_not_be_used_as_production_authority": True,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "authoritative_524_evidence": {
            "weekly_confidence_signed_error": -0.5,
            "profile_confidence_signed_error": -0.24,
            "confidence_candidate_paths": [
                item["path"]
                for item in report_524.get(
                    "confidence_minus_0_24_candidate_paths",
                    [],
                )
            ],
        },
        "intervention_design": {
            "BASELINE": "No mutation.",
            "WEEKLY_ONLY": (
                "Replace only mt['states']['1w'].confidence with the frozen weekly confidence "
                "after native MT analyze returns; leave mt['confidence'] unchanged."
            ),
            "AGGREGATE_ONLY": (
                "Replace only mt['confidence'] with the frozen profile confidence; "
                "leave weekly state confidence unchanged."
            ),
            "WEEKLY_AND_AGGREGATE": (
                "Apply both controlled MT-output interventions before the rest of "
                "StockIntelligenceService executes."
            ),
            "purpose": (
                "Determine whether weekly confidence is re-read downstream, whether "
                "aggregate MT confidence is the direct source of profile confidence, "
                "and whether confidence repair alone restores score/state parity."
            ),
        },
        "native_mt_class_source": mt_source,
        "monthly_bundle_count": len(records),
        "arm_summaries": summaries,
        "causal_findings": {
            "baseline_reproduced": baseline_reproduced,
            "weekly_only_does_not_recompute_profile_confidence": (
                weekly_only_does_not_recompute_profile_confidence
            ),
            "aggregate_intervention_restores_profile_confidence": (
                aggregate_intervention_restores_profile_confidence
            ),
            "both_intervention_restores_weekly_and_profile_confidence": (
                both_intervention_restores_weekly_and_profile_confidence
            ),
            "confidence_lineage_isolated_to_mt_aggregate_output": (
                confidence_lineage_isolated_to_mt_aggregate_output
            ),
            "downstream_score_parity_after_confidence_repair": (
                downstream_score_parity_after_confidence_repair
            ),
            "full_state_parity_after_confidence_repair": (
                full_state_parity_after_confidence_repair
            ),
        },
        "records": records,
        "forensic_conclusion": forensic_conclusion,
        "controlled_exact_input_parity_certified": (
            controlled_exact_input_parity_certified
        ),
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print(
        "=== M77.19.6.5.2.5 MONTHLY COMPONENT CAUSAL REPLAY CERTIFICATION ==="
    )
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("native_compare_profile_is_semantic_authority: True")
    print("monthly_bundle_count:", len(records))
    print("baseline_summary:", summaries["BASELINE"])
    print("weekly_only_summary:", summaries["WEEKLY_ONLY"])
    print("aggregate_only_summary:", summaries["AGGREGATE_ONLY"])
    print("weekly_and_aggregate_summary:", summaries["WEEKLY_AND_AGGREGATE"])
    print("causal_findings:", report["causal_findings"])
    print("forensic_conclusion:", forensic_conclusion)
    print(
        "controlled_exact_input_parity_certified:",
        controlled_exact_input_parity_certified,
    )
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
