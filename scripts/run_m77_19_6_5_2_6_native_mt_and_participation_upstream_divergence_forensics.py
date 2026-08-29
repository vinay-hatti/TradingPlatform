#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.6-NATIVE-MT-AND-PARTICIPATION-UPSTREAM-DIVERGENCE-FORENSICS-1.0"

EXPECTED_524_REPORT_SHA256 = "9147873baa5baa3e19e528d6b47d125450316e3a32dfc595ec6064eb2093eb96"
EXPECTED_525_REPORT_SHA256 = "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"

PARITY_TOLERANCE = 1e-9

CONFIDENCE_DERIVED_PREFIXES = (
    "confidence",
    "scores.confidence",
    "decision_intelligence.explainability.decision_readiness.components.confidence",
)

UPSTREAM_DOMAIN_RULES = (
    ("MT_WEEKLY", ("timeframe_states.1w", "weekly", "1w.")),
    ("PARTICIPATION", ("participation", "adl", "advance_decline", "volume_participation")),
    ("STRUCTURE", ("structure", "structural", "trend_structure")),
    ("LEVELS", ("support", "resistance", "levels", "level_")),
    ("MOMENTUM", ("momentum", "rsi", "macd", "ema", "sma", "atr")),
    ("MANAGEMENT", ("management", "trade_plan", "target", "stop")),
    ("DECISION", ("decision_intelligence", "decision_readiness", "scores.")),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_report(path: Path, expected_sha: str, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"FAIL CLOSED: {label} report missing: {path}")
    actual = sha256_file(path)
    if actual != expected_sha:
        raise SystemExit(f"FAIL CLOSED: {label} report SHA drift: {actual}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"FAIL CLOSED: {label} report is not a JSON object")
    return data


def flatten(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            p = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten(value, p)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            p = f"{prefix}.{idx}" if prefix else str(idx)
            yield from flatten(value, p)
    else:
        yield prefix, obj


def collect_path_evidence(report_524: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    seen = set()

    # Prefer the authoritative constant-numeric block when present.
    for item in report_524.get("constant_numeric_component_deltas", []) or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if not path or path in seen:
            continue
        seen.add(path)
        evidence.append(
            {
                "path": path,
                "source": "constant_numeric_component_deltas",
                "count": item.get("count"),
                "unique_signed_errors": item.get("unique_signed_errors"),
                "is_constant_numeric": True,
            }
        )

    # Add any other explicit path/difference structures without depending on
    # one historical schema.
    for flat_path, value in flatten(report_524):
        key = flat_path.lower()
        if not isinstance(value, str):
            continue
        if not (
            key.endswith(".path")
            or "diverg" in key
            or "difference" in key
            or "mismatch" in key
        ):
            continue
        candidate = value.strip()
        if "." not in candidate or candidate in seen:
            continue
        seen.add(candidate)
        evidence.append(
            {
                "path": candidate,
                "source": flat_path,
                "count": None,
                "unique_signed_errors": None,
                "is_constant_numeric": False,
            }
        )

    return evidence


def classify_domain(path: str) -> str:
    low = path.lower()
    for domain, needles in UPSTREAM_DOMAIN_RULES:
        if any(needle in low for needle in needles):
            return domain
    return "OTHER"


def is_confidence_derived(path: str) -> bool:
    low = path.lower()
    return any(low == p or low.startswith(p + ".") for p in CONFIDENCE_DERIVED_PREFIXES)


def parse_mt_formula(source: str) -> dict[str, Any]:
    normalized = " ".join(source.split())
    confidence_unweighted_mean = bool(
        re.search(
            r"confidence['\"]?\s*:\s*round\(sum\(x\.confidence for x in states\.values\(\)\)/len\(states\),2\)",
            normalized,
        )
    )
    direction_uses_weights = (
        "self.weights.get(k,.1)*self.signed[v.direction]" in normalized
        or "self.weights.get(k, .1) * self.signed[v.direction]" in normalized
    )
    confidence_uses_weights = bool(
        re.search(r"confidence.{0,120}weights", normalized, flags=re.I)
    )

    try:
        tree = ast.parse(source)
        syntax_valid = True
        function_names = [
            n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
        ]
    except SyntaxError:
        syntax_valid = False
        function_names = []

    return {
        "source_syntax_valid": syntax_valid,
        "function_names": function_names,
        "confidence_formula_detected_as_unweighted_mean": confidence_unweighted_mean,
        "direction_formula_uses_timeframe_weights": direction_uses_weights,
        "confidence_formula_uses_timeframe_weights": confidence_uses_weights,
        "formula_semantics": (
            "AVAILABLE_STATE_UNWEIGHTED_CONFIDENCE_MEAN"
            if confidence_unweighted_mean
            else "FORMULA_NOT_MACHINE_CONFIRMED"
        ),
    }


def arm_invariants(report_525: dict[str, Any]) -> dict[str, Any]:
    summaries = report_525.get("arm_summaries") or {}
    base = summaries.get("BASELINE") or {}
    weekly = summaries.get("WEEKLY_ONLY") or {}
    agg = summaries.get("AGGREGATE_ONLY") or {}
    both = summaries.get("WEEKLY_AND_AGGREGATE") or {}

    score_dist = base.get("score_signed_error_distribution_2dp")

    return {
        "baseline_weekly_delta_is_minus_0_5_all_48": (
            base.get("weekly_confidence_signed_error_distribution_2dp") == {"-0.5": 48}
            or base.get("weekly_confidence_signed_error_distribution_2dp") == {-0.5: 48}
        ),
        "baseline_profile_delta_is_minus_0_24_all_48": (
            base.get("confidence_signed_error_distribution_2dp") == {"-0.24": 48}
            or base.get("confidence_signed_error_distribution_2dp") == {-0.24: 48}
        ),
        "weekly_only_repairs_weekly_48": weekly.get("weekly_confidence_exact_count") == 48,
        "weekly_only_does_not_repair_profile": weekly.get("profile_confidence_exact_count") == 0,
        "aggregate_only_repairs_profile_48": agg.get("profile_confidence_exact_count") == 48,
        "both_repairs_weekly_and_profile_48": (
            both.get("weekly_confidence_exact_count") == 48
            and both.get("profile_confidence_exact_count") == 48
        ),
        "score_distribution_identical_after_both_confidence_repairs": (
            score_dist == both.get("score_signed_error_distribution_2dp")
        ),
        "state_hashes_remain_zero_after_both_confidence_repairs": (
            both.get("state_hash_exact_count") == 0
        ),
        "overall_score_exact_count_remains_two": (
            base.get("overall_score_exact_count") == 2
            and both.get("overall_score_exact_count") == 2
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--report-524",
        default="reports/m77_19_6_5_2_4_monthly_feature_confidence_component_forensics.json",
    )
    parser.add_argument(
        "--report-525",
        default="reports/m77_19_6_5_2_5_monthly_component_causal_replay_certification.json",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_2_6_native_mt_and_participation_upstream_divergence_forensics.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    path_524 = root / args.report_524
    path_525 = root / args.report_525

    report_524 = require_report(
        path_524, EXPECTED_524_REPORT_SHA256, "M77.19.6.5.2.4"
    )
    report_525 = require_report(
        path_525, EXPECTED_525_REPORT_SHA256, "M77.19.6.5.2.5"
    )

    if report_525.get("forensic_conclusion") != (
        "MONTHLY_MT_CONFIDENCE_LINEAGE_CAUSALLY_CONFIRMED_BUT_FULL_PARITY_HAS_ADDITIONAL_UPSTREAM_DIVERGENCES"
    ):
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.5 causal conclusion not authoritative")

    if report_525.get("controlled_exact_input_parity_certified") is not False:
        raise SystemExit("FAIL CLOSED: prior parity state is not blocked")

    mt_source = str(report_525.get("native_mt_class_source") or "")
    if not mt_source:
        raise SystemExit("FAIL CLOSED: native MT source absent from M77.19.6.5.2.5")

    formula = parse_mt_formula(mt_source)
    invariants = arm_invariants(report_525)

    if not all(invariants.values()):
        raise SystemExit(
            "FAIL CLOSED: M77.19.6.5.2.5 causal invariants did not reproduce"
        )

    evidence = collect_path_evidence(report_524)

    classified = []
    for item in evidence:
        path = item["path"]
        record = dict(item)
        record["domain"] = classify_domain(path)
        record["confidence_derived"] = is_confidence_derived(path)
        classified.append(record)

    domain_counts = Counter(item["domain"] for item in classified)

    # Remaining upstream candidates explicitly exclude known downstream
    # confidence propagation paths. MT weekly confidence is retained because
    # M77.19.6.5.2.5 proved it is upstream of aggregate/profile confidence.
    remaining = [
        item
        for item in classified
        if not item["confidence_derived"]
    ]

    priority_order = {
        "MT_WEEKLY": 0,
        "PARTICIPATION": 1,
        "STRUCTURE": 2,
        "LEVELS": 3,
        "MOMENTUM": 4,
        "MANAGEMENT": 5,
        "DECISION": 6,
        "OTHER": 7,
    }

    remaining.sort(
        key=lambda item: (
            priority_order.get(item["domain"], 99),
            0 if item["is_constant_numeric"] else 1,
            item["path"],
        )
    )

    mt_candidates = [x for x in remaining if x["domain"] == "MT_WEEKLY"]
    participation_candidates = [
        x for x in remaining if x["domain"] == "PARTICIPATION"
    ]

    mt_weekly_path_present = any(
        x["path"] == "timeframe_states.1w.confidence"
        for x in mt_candidates
    )

    # The source itself establishes a crucial semantic point:
    # weights affect directional signed score, while confidence is an
    # unweighted mean of available state confidences.
    mt_semantics_confirmed = (
        formula["confidence_formula_detected_as_unweighted_mean"]
        and formula["direction_formula_uses_timeframe_weights"]
        and not formula["confidence_formula_uses_timeframe_weights"]
    )

    confidence_root_scope = (
        "TIMEFRAME_STATE_CONFIDENCE_SEMANTICS_OR_AVAILABLE_STATE_SET"
        if mt_semantics_confirmed and mt_weekly_path_present
        else "MT_CONFIDENCE_FORMULA_OR_STATE_INPUTS_REQUIRE_FURTHER_SOURCE_FORENSICS"
    )

    if participation_candidates:
        participation_scope = "EXPLICIT_PARTICIPATION_PATHS_PRESENT_IN_524"
    else:
        participation_scope = (
            "NO_EXPLICIT_PARTICIPATION_PATH_DISCOVERED_BY_SCHEMA_AGNOSTIC_PATH_SCAN;"
            " retain participation as source-level candidate only if 524 narrative/source evidence says so"
        )

    report = {
        "version": VERSION,
        "source_authorities": {
            "m77_19_6_5_2_4": {
                "path": str(path_524),
                "sha256": EXPECTED_524_REPORT_SHA256,
            },
            "m77_19_6_5_2_5": {
                "path": str(path_525),
                "sha256": EXPECTED_525_REPORT_SHA256,
            },
        },
        "governance": {
            "research_only": True,
            "database_access": "NONE",
            "database_writes": False,
            "production_code_mutation": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "m77_19_6_5_2_5_causal_invariants": invariants,
        "native_mt_formula_forensics": formula,
        "native_mt_source": mt_source,
        "upstream_path_inventory": {
            "discovered_path_count": len(classified),
            "domain_counts": dict(sorted(domain_counts.items())),
            "all_paths": classified,
            "remaining_non_downstream_confidence_candidates": remaining,
            "mt_weekly_candidates": mt_candidates,
            "participation_candidates": participation_candidates,
        },
        "causal_interpretation": {
            "mt_weekly_path_present": mt_weekly_path_present,
            "native_mt_semantics_confirmed": mt_semantics_confirmed,
            "confidence_root_scope": confidence_root_scope,
            "participation_scope": participation_scope,
            "weekly_only_intervention_meaning": (
                "The M77.19.6.5.2.5 WEEKLY_ONLY mutation occurred after native mt.analyze() "
                "had already calculated aggregate confidence, so unchanged profile confidence "
                "does not prove weekly confidence is irrelevant to the native formula. It proves "
                "there is no downstream recomputation from the mutated weekly state."
            ),
            "aggregate_only_intervention_meaning": (
                "Replacing mt['confidence'] repairs profile confidence 48/48, proving direct "
                "profile-confidence lineage from native MT aggregate output."
            ),
            "score_independence_from_confidence_intervention": (
                "The entire overall-score signed-error distribution is identical before and "
                "after weekly+aggregate confidence repair; therefore the remaining score "
                "divergence is causally independent of these synthetic confidence corrections."
            ),
            "state_independence_from_confidence_intervention": (
                "State-hash parity remains 0/48 after weekly+aggregate confidence repair; "
                "additional upstream state/feature divergences are mandatory."
            ),
        },
        "forensic_conclusion": (
            "MONTHLY_CONFIDENCE_LINEAGE_CLOSED_AT_MT_AGGREGATE_OUTPUT;"
            " WEEKLY_STATE_CONFIDENCE_REMAINS_AN_UPSTREAM_STATE_SEMANTICS_DIVERGENCE;"
            " SCORE_AND_STATE_PARITY_REQUIRE_NON_CONFIDENCE_UPSTREAM_FORENSICS"
        ),
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": (
            "BUILD_M77_19_6_5_2_7_NATIVE_TIMEFRAME_STATE_AND_PARTICIPATION_CAUSAL_INTERVENTION_REPLAY"
        ),
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.6 NATIVE MT & PARTICIPATION UPSTREAM DIVERGENCE FORENSICS ===")
    print("database_access: NONE")
    print("source_524_sha_pinned: True")
    print("source_525_sha_pinned: True")
    print("native_mt_formula_forensics:", formula)
    print("causal_invariants:", invariants)
    print("discovered_upstream_path_count:", len(classified))
    print("domain_counts:", dict(sorted(domain_counts.items())))
    print("mt_weekly_candidate_count:", len(mt_candidates))
    print("participation_candidate_count:", len(participation_candidates))
    print("confidence_root_scope:", confidence_root_scope)
    print("forensic_conclusion:", report["forensic_conclusion"])
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("report:", output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
