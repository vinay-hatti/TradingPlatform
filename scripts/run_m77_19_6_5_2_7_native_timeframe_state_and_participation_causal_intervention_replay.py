#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

VERSION = "M77.19.6.5.2.7-NATIVE-TIMEFRAME-STATE-AND-PARTICIPATION-CAUSAL-INTERVENTION-REPLAY-1.0"

NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

EXPECTED_525_REPORT_SHA256 = "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"
EXPECTED_526_REPORT_SHA256 = "80a47e00da8951f15dec66c156f312601e6261bdf37430a1da3dae7d83301187"

PARITY_TOLERANCE = 1e-9

WEEKLY_CANDIDATE_PATHS = (
    "timeframe_states.1w.confidence",
    "timeframe_states.1w.evidence.ema50",
)

PARTICIPATION_RAW_EVIDENCE_PATHS = (
    "participation.evidence.adl",
    "participation.evidence.obv_normalized",
    "participation.evidence.up_down_volume_ratio",
)

PARTICIPATION_COMPONENT_PATHS = (
    "participation.evidence.adl",
    "participation.evidence.obv_normalized",
    "participation.evidence.up_down_volume_ratio",
    "participation.score",
    "participation.state",
    "participation.conviction",
    "participation.deterioration_risk",
)

ARMS = (
    "BASELINE",
    "WEEKLY_CANDIDATES",
    "PARTICIPATION_EVIDENCE_ONLY",
    "PARTICIPATION_COMPONENT",
    "WEEKLY_AND_PARTICIPATION_COMPONENT",
)


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


def import_native(root: Path):
    path = root / NATIVE_RUNNER_REL
    if not path.exists():
        raise SystemExit("FAIL CLOSED: native runner missing")

    actual = sha256_file(path)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")

    spec = importlib.util.spec_from_file_location("m77_native_527", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in ("call_profile", "compare_profile", "StockIntelligenceService"):
        if not hasattr(module, name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")

    return module


def require_report(
    root: Path,
    rel: str,
    expected_sha: str,
    expected_conclusion: str | None = None,
):
    path = root / rel
    if not path.exists():
        raise SystemExit(f"FAIL CLOSED: required authority missing: {rel}")

    actual = sha256_file(path)
    if actual != expected_sha:
        raise SystemExit(f"FAIL CLOSED: authority SHA drift for {rel}: {actual}")

    report = load_json(path)

    if expected_conclusion is not None and report.get("forensic_conclusion") != expected_conclusion:
        raise SystemExit(f"FAIL CLOSED: authority conclusion drift for {rel}")

    return path, report


def validate_526(report: dict[str, Any]) -> None:
    if report.get("controlled_exact_input_parity_certified") is not False:
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.6 parity state is not blocked")

    if report.get("full_23_year_reconstruction_authorized") is not False:
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.6 reconstruction state drift")

    governance = report.get("governance") or {}
    if governance.get("parity_tolerance") != PARITY_TOLERANCE:
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.6 parity tolerance drift")

    inventory = report.get("upstream_path_inventory") or {}
    mt_paths = {item.get("path") for item in inventory.get("mt_weekly_candidates", [])}
    p_paths = {item.get("path") for item in inventory.get("participation_candidates", [])}

    missing_mt = set(WEEKLY_CANDIDATE_PATHS) - mt_paths
    if missing_mt:
        raise SystemExit(f"FAIL CLOSED: missing MT candidates in 526: {sorted(missing_mt)}")

    expected_participation = set(PARTICIPATION_COMPONENT_PATHS)
    missing_participation = expected_participation - p_paths
    if missing_participation:
        raise SystemExit(
            f"FAIL CLOSED: missing participation candidates in 526: "
            f"{sorted(missing_participation)}"
        )


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


def get_member(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def has_member(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def set_member(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = copy.deepcopy(value)
    else:
        setattr(obj, key, copy.deepcopy(value))


def get_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if isinstance(current, (list, tuple)) and part.isdigit():
            current = current[int(part)]
        else:
            current = get_member(current, part)
    return current


def set_path(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            current = get_member(current, part)

    leaf = parts[-1]
    if isinstance(current, list) and leaf.isdigit():
        current[int(leaf)] = copy.deepcopy(value)
    else:
        set_member(current, leaf, value)


def equivalent(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= PARITY_TOLERANCE
    return a == b


def weekly_state(profile: Any) -> Any:
    states = get_member(profile, "timeframe_states")
    if isinstance(states, dict):
        return states["1w"]
    return get_member(states, "1w")


def get_weekly_candidate(profile: Any, path: str) -> Any:
    suffix = path.removeprefix("timeframe_states.1w.")
    return get_path(weekly_state(profile), suffix)


def participation_obj(profile: Any) -> Any:
    return get_member(profile, "participation")


def get_participation_candidate(profile: Any, path: str) -> Any:
    suffix = path.removeprefix("participation.")
    return get_path(participation_obj(profile), suffix)


def patch_mt_candidates(
    service: Any,
    frozen_profile: dict[str, Any],
) -> Callable[[], None]:
    original = service.mt.analyze

    def wrapped(data_by_timeframe):
        result = original(data_by_timeframe)
        if not isinstance(result, dict):
            raise RuntimeError("MT analyze did not return dict")

        states = result.get("states")
        if not isinstance(states, dict) or "1w" not in states:
            raise RuntimeError("MT analyze missing states['1w']")

        frozen_weekly = frozen_profile["timeframe_states"]["1w"]
        state = states["1w"]

        set_path(state, "confidence", frozen_weekly["confidence"])
        set_path(state, "evidence.ema50", frozen_weekly["evidence"]["ema50"])

        # Recompute aggregate confidence using the pinned native semantics:
        # unweighted arithmetic mean of all currently available state confidences.
        confidences = [float(get_path(v, "confidence")) for v in states.values()]
        if not confidences:
            raise RuntimeError("no MT states available after intervention")
        result["confidence"] = round(sum(confidences) / len(confidences), 2)

        return result

    service.mt.analyze = wrapped

    def restore():
        service.mt.analyze = original

    return restore


def patch_participation(
    service: Any,
    frozen_profile: dict[str, Any],
    paths: tuple[str, ...],
) -> Callable[[], None]:
    original = service.part.analyze
    frozen_participation = frozen_profile["participation"]

    def wrapped(primary):
        result = original(primary)

        for full_path in paths:
            suffix = full_path.removeprefix("participation.")
            frozen_value = get_path(frozen_participation, suffix)
            set_path(result, suffix, frozen_value)

        return result

    service.part.analyze = wrapped

    def restore():
        service.part.analyze = original

    return restore


def profile_metrics(native, profile, frozen_output, frozen_profile):
    comparison = native.compare_profile(profile, frozen_output)

    weekly_results = {}
    for path in WEEKLY_CANDIDATE_PATHS:
        isolated = get_weekly_candidate(profile, path)
        frozen = get_path(frozen_profile, path)
        weekly_results[path] = {
            "isolated": isolated,
            "frozen": frozen,
            "exact": equivalent(isolated, frozen),
        }

    participation_results = {}
    for path in PARTICIPATION_COMPONENT_PATHS:
        isolated = get_participation_candidate(profile, path)
        frozen = get_path(frozen_profile, path)
        participation_results[path] = {
            "isolated": isolated,
            "frozen": frozen,
            "exact": equivalent(isolated, frozen),
        }

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
        "state_hash_match": bool(comparison["state_hash_match"]),
        "isolated_overall_score": float(comparison["isolated"]["overall_score"]),
        "stored_overall_score": float(comparison["stored"]["overall_score"]),
        "isolated_confidence": float(comparison["isolated"]["confidence"]),
        "stored_confidence": float(comparison["stored"]["confidence"]),
        "weekly_candidates": weekly_results,
        "participation_candidates": participation_results,
    }


def run_arm(
    native,
    symbol: str,
    rows: list[dict[str, Any]],
    as_of: dt.date,
    sessions: set[dt.date],
    frozen_output: dict[str, Any],
    frozen_profile: dict[str, Any],
    arm: str,
):
    service = native.StockIntelligenceService()
    restores: list[Callable[[], None]] = []

    if arm in ("WEEKLY_CANDIDATES", "WEEKLY_AND_PARTICIPATION_COMPONENT"):
        restores.append(patch_mt_candidates(service, frozen_profile))

    if arm == "PARTICIPATION_EVIDENCE_ONLY":
        restores.append(
            patch_participation(
                service,
                frozen_profile,
                PARTICIPATION_RAW_EVIDENCE_PATHS,
            )
        )

    if arm in ("PARTICIPATION_COMPONENT", "WEEKLY_AND_PARTICIPATION_COMPONENT"):
        restores.append(
            patch_participation(
                service,
                frozen_profile,
                PARTICIPATION_COMPONENT_PATHS,
            )
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
        for restore in reversed(restores):
            restore()

    if profile is None:
        raise RuntimeError(f"{arm} profile ineligible for {symbol}")

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

    weekly_exact_by_path = {
        path: sum(v["weekly_candidates"][path]["exact"] for v in values)
        for path in WEEKLY_CANDIDATE_PATHS
    }

    participation_exact_by_path = {
        path: sum(v["participation_candidates"][path]["exact"] for v in values)
        for path in PARTICIPATION_COMPONENT_PATHS
    }

    return {
        "count": len(values),
        "direction_match_pct": (
            100.0 * sum(v["direction_match"] for v in values) / len(values)
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
        "max_profile_confidence_abs_error": max(
            v["confidence_abs_error"] for v in values
        ),
        "max_score_abs_error": max(
            v["score_abs_error"] for v in values
        ),
        "weekly_candidate_exact_counts": weekly_exact_by_path,
        "participation_candidate_exact_counts": participation_exact_by_path,
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
    }


def delta_count(after: dict[str, Any], before: dict[str, Any], key: str) -> int:
    return int(after[key]) - int(before[key])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--bundle-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_7_native_timeframe_state_and_participation_causal_intervention_replay.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    source_525, report_525 = require_report(
        root,
        "reports/m77_19_6_5_2_5_monthly_component_causal_replay_certification.json",
        EXPECTED_525_REPORT_SHA256,
        "MONTHLY_MT_CONFIDENCE_LINEAGE_CAUSALLY_CONFIRMED_BUT_FULL_PARITY_HAS_ADDITIONAL_UPSTREAM_DIVERGENCES",
    )

    source_526, report_526 = require_report(
        root,
        "reports/m77_19_6_5_2_6_native_mt_and_participation_upstream_divergence_forensics.json",
        EXPECTED_526_REPORT_SHA256,
        (
            "MONTHLY_CONFIDENCE_LINEAGE_CLOSED_AT_MT_AGGREGATE_OUTPUT;"
            " WEEKLY_STATE_CONFIDENCE_REMAINS_AN_UPSTREAM_STATE_SEMANTICS_DIVERGENCE;"
            " SCORE_AND_STATE_PARITY_REQUIRE_NON_CONFIDENCE_UPSTREAM_FORENSICS"
        ),
    )
    validate_526(report_526)

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
        for arm in ARMS:
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

    summaries = {arm: summarize(records, arm) for arm in ARMS}

    baseline = summaries["BASELINE"]
    weekly = summaries["WEEKLY_CANDIDATES"]
    raw_part = summaries["PARTICIPATION_EVIDENCE_ONLY"]
    part = summaries["PARTICIPATION_COMPONENT"]
    combined = summaries["WEEKLY_AND_PARTICIPATION_COMPONENT"]

    prior_baseline = (report_525.get("arm_summaries") or {}).get("BASELINE") or {}

    baseline_reproduced = (
        baseline["profile_confidence_exact_count"]
        == prior_baseline.get("profile_confidence_exact_count")
        and baseline["overall_score_exact_count"]
        == prior_baseline.get("overall_score_exact_count")
        and baseline["state_hash_exact_count"]
        == prior_baseline.get("state_hash_exact_count")
        and baseline["score_signed_error_distribution_2dp"]
        == prior_baseline.get("score_signed_error_distribution_2dp")
    )

    weekly_candidates_exact_48 = all(
        weekly["weekly_candidate_exact_counts"].get(path) == 48
        for path in WEEKLY_CANDIDATE_PATHS
    )

    weekly_native_recompute_restores_profile_confidence = (
        weekly["profile_confidence_exact_count"] == 48
    )

    participation_raw_evidence_exact_48 = all(
        raw_part["participation_candidate_exact_counts"].get(path) == 48
        for path in PARTICIPATION_RAW_EVIDENCE_PATHS
    )

    participation_component_exact_48 = all(
        part["participation_candidate_exact_counts"].get(path) == 48
        for path in PARTICIPATION_COMPONENT_PATHS
    )

    weekly_score_gain = delta_count(weekly, baseline, "overall_score_exact_count")
    weekly_state_gain = delta_count(weekly, baseline, "state_hash_exact_count")

    raw_part_score_gain = delta_count(
        raw_part, baseline, "overall_score_exact_count"
    )
    raw_part_state_gain = delta_count(
        raw_part, baseline, "state_hash_exact_count"
    )

    part_score_gain = delta_count(part, baseline, "overall_score_exact_count")
    part_state_gain = delta_count(part, baseline, "state_hash_exact_count")

    combined_score_gain = delta_count(
        combined, baseline, "overall_score_exact_count"
    )
    combined_state_gain = delta_count(
        combined, baseline, "state_hash_exact_count"
    )

    participation_component_has_downstream_score_effect = (
        part["score_signed_error_distribution_2dp"]
        != baseline["score_signed_error_distribution_2dp"]
        or part_score_gain != 0
    )

    combined_has_additional_effect_over_weekly = (
        combined["score_signed_error_distribution_2dp"]
        != weekly["score_signed_error_distribution_2dp"]
        or combined["state_hash_exact_count"] != weekly["state_hash_exact_count"]
    )

    controlled_exact_input_parity_certified = (
        weekly_candidates_exact_48
        and combined["profile_confidence_exact_count"] == 48
        and combined["overall_score_exact_count"] == 48
        and combined["state_hash_exact_count"] == 48
    )

    if controlled_exact_input_parity_certified:
        forensic_conclusion = (
            "MONTHLY_NATIVE_WEEKLY_STATE_AND_PARTICIPATION_COMPONENTS_CAUSALLY_RESTORE_FULL_PARITY"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_8_CONTROLLED_EXACT_INPUT_PARITY_CERTIFICATION"
        )
    elif combined_has_additional_effect_over_weekly:
        forensic_conclusion = (
            "MONTHLY_WEEKLY_STATE_AND_PARTICIPATION_HAVE_CAUSAL_DOWNSTREAM_EFFECT_BUT_ADDITIONAL_STRUCTURE_LEVEL_DIVERGENCES_REMAIN"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_8_STRUCTURE_AND_LEVEL_GENERATION_UPSTREAM_CAUSAL_FORENSICS"
        )
    elif participation_component_has_downstream_score_effect:
        forensic_conclusion = (
            "MONTHLY_PARTICIPATION_COMPONENT_CAUSALLY_AFFECTS_SCORE_BUT_DOES_NOT_CLOSE_STATE_PARITY"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_8_STRUCTURE_AND_LEVEL_GENERATION_UPSTREAM_CAUSAL_FORENSICS"
        )
    else:
        forensic_conclusion = (
            "MONTHLY_WEEKLY_STATE_REPAIR_CONFIRMED_BUT_PARTICIPATION_CANDIDATES_DO_NOT_EXPLAIN_REMAINING_SCORE_STATE_DIVERGENCE"
        )
        next_step = (
            "BUILD_M77_19_6_5_2_8_STRUCTURE_AND_LEVEL_GENERATION_UPSTREAM_CAUSAL_FORENSICS"
        )

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_5": {
                "path": str(source_525),
                "sha256": EXPECTED_525_REPORT_SHA256,
            },
            "m77_19_6_5_2_6": {
                "path": str(source_526),
                "sha256": EXPECTED_526_REPORT_SHA256,
            },
            "native_runner": {
                "path": str(root / NATIVE_RUNNER_REL),
                "sha256": EXPECTED_NATIVE_RUNNER_SHA256,
            },
        },
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
        "intervention_design": {
            "BASELINE": "No mutation.",
            "WEEKLY_CANDIDATES": {
                "paths": list(WEEKLY_CANDIDATE_PATHS),
                "method": (
                    "Replace the two M77.19.6.5.2.6 weekly-state candidate values "
                    "inside native mt.analyze() output, then recompute mt['confidence'] "
                    "using the pinned native unweighted-available-state mean."
                ),
            },
            "PARTICIPATION_EVIDENCE_ONLY": {
                "paths": list(PARTICIPATION_RAW_EVIDENCE_PATHS),
                "method": (
                    "Replace only the three raw participation evidence values after "
                    "ParticipationEngine.analyze returns. This intentionally does not "
                    "rewrite derived participation state/score fields and tests whether "
                    "downstream services re-read raw evidence."
                ),
            },
            "PARTICIPATION_COMPONENT": {
                "paths": list(PARTICIPATION_COMPONENT_PATHS),
                "method": (
                    "Replace the seven identified participation component-output paths "
                    "at the StockIntelligenceService participation boundary, before "
                    "structure-zone building, scoring, trade-plan construction, "
                    "certification, and Decision Intelligence."
                ),
            },
            "WEEKLY_AND_PARTICIPATION_COMPONENT": {
                "weekly_paths": list(WEEKLY_CANDIDATE_PATHS),
                "participation_paths": list(PARTICIPATION_COMPONENT_PATHS),
                "method": (
                    "Apply both upstream component interventions in the same replay."
                ),
            },
        },
        "monthly_bundle_count": len(records),
        "arm_summaries": summaries,
        "causal_findings": {
            "baseline_reproduced": baseline_reproduced,
            "weekly_candidates_exact_48": weekly_candidates_exact_48,
            "weekly_native_recompute_restores_profile_confidence": (
                weekly_native_recompute_restores_profile_confidence
            ),
            "participation_raw_evidence_exact_48": participation_raw_evidence_exact_48,
            "participation_component_exact_48": participation_component_exact_48,
            "weekly_score_exact_gain_vs_baseline": weekly_score_gain,
            "weekly_state_hash_gain_vs_baseline": weekly_state_gain,
            "participation_raw_score_exact_gain_vs_baseline": raw_part_score_gain,
            "participation_raw_state_hash_gain_vs_baseline": raw_part_state_gain,
            "participation_component_score_exact_gain_vs_baseline": part_score_gain,
            "participation_component_state_hash_gain_vs_baseline": part_state_gain,
            "combined_score_exact_gain_vs_baseline": combined_score_gain,
            "combined_state_hash_gain_vs_baseline": combined_state_gain,
            "participation_component_has_downstream_score_effect": (
                participation_component_has_downstream_score_effect
            ),
            "combined_has_additional_effect_over_weekly": (
                combined_has_additional_effect_over_weekly
            ),
            "full_score_parity_after_combined_repair": (
                combined["overall_score_exact_count"] == 48
            ),
            "full_state_parity_after_combined_repair": (
                combined["state_hash_exact_count"] == 48
            ),
        },
        "records": records,
        "forensic_conclusion": forensic_conclusion,
        "controlled_exact_input_parity_certified": controlled_exact_input_parity_certified,
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
        "=== M77.19.6.5.2.7 NATIVE TIMEFRAME STATE & PARTICIPATION "
        "CAUSAL INTERVENTION REPLAY ==="
    )
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("native_compare_profile_is_semantic_authority: True")
    print("monthly_bundle_count:", len(records))
    for arm in ARMS:
        print(f"{arm.lower()}_summary:", summaries[arm])
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
