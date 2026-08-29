#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

VERSION = "M77.19.6.5.2.20-NATIVE-OBSERVABLE-TRIGGER-COLLATERAL-IMPACT-FORENSICS-1.0"

REPORT_5219_REL = "reports/m77_19_6_5_2_19_native_observable_consolidation_trigger_causal_replay.json"
EXPECTED_REPORT_5219_SHA256 = "9e024506d6c519b73ac9c32d8e11b350a35329627e58e5243fed03e1911a52c7"

RUNNER_5219_REL = "scripts/run_m77_19_6_5_2_19_native_observable_consolidation_trigger_causal_replay.py"
EXPECTED_RUNNER_5219_SHA256 = "1a47684e03de666163366baaa9c852bf0e9c24325c4109bb45ad3ef93dbea1f0"

EXPECTED_MONTHLY_BUNDLE_COUNT = 48
EXPECTED_NATIVE_EXACT = 1338
EXPECTED_NATIVE_MISSING = 67
EXPECTED_SPLIT_EXACT = 549
EXPECTED_SPLIT_MISSING = 560
EXPECTED_PRESERVE_EXACT = 1222
EXPECTED_PRESERVE_MISSING = 150

TARGET_SYMBOLS = ("AES", "ANET", "ATO")
ARMS = (
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

def validate_5219(report: dict[str, Any]) -> dict[str, Any]:
    arms = report.get("arm_summaries") or {}
    native = arms.get("NATIVE_CONTROL") or {}
    split = arms.get("OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE") or {}
    preserve = arms.get("OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT") or {}
    winner = report.get("winner_analysis") or {}

    checks = {
        "monthly_bundle_count_48": report.get("monthly_bundle_count") == EXPECTED_MONTHLY_BUNDLE_COUNT,
        "native_exact_1338": native.get("exact_frozen_match_count") == EXPECTED_NATIVE_EXACT,
        "native_missing_67": native.get("missing_beyond_0_3pct_count") == EXPECTED_NATIVE_MISSING,
        "split_exact_549": split.get("exact_frozen_match_count") == EXPECTED_SPLIT_EXACT,
        "split_missing_560": split.get("missing_beyond_0_3pct_count") == EXPECTED_SPLIT_MISSING,
        "split_targets_3": split.get("target_recovered_count") == 3,
        "preserve_exact_1222": preserve.get("exact_frozen_match_count") == EXPECTED_PRESERVE_EXACT,
        "preserve_missing_150": preserve.get("missing_beyond_0_3pct_count") == EXPECTED_PRESERVE_MISSING,
        "preserve_targets_1": preserve.get("target_recovered_count") == 1,
        "winner_globally_non_degrading_false": winner.get("globally_non_degrading") is False,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "NATIVE_OBSERVABLE_TRIGGER_RECOVERS_ALL_CAUSAL_TARGETS_BUT_GLOBAL_PARITY_TRADEOFF_REMAINS",
        "semantic_not_promoted": report.get("candidate_semantic_promoted") is False,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.19 authority validation failed: {checks}")
    return checks

def sign_bucket(value: int) -> str:
    if value > 0:
        return "IMPROVED"
    if value < 0:
        return "WORSENED"
    return "UNCHANGED"

def describe(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "sum": 0,
        }
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
        "sum": sum(values),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    report_path = require_file(
        root, REPORT_5219_REL, EXPECTED_REPORT_5219_SHA256, "M77.19.6.5.2.19 report"
    )
    require_file(
        root, RUNNER_5219_REL, EXPECTED_RUNNER_5219_SHA256, "M77.19.6.5.2.19 runner"
    )
    source = load_json(report_path)
    authority = validate_5219(source)

    records = source.get("records") or []
    if len(records) != EXPECTED_MONTHLY_BUNDLE_COUNT:
        raise SystemExit(
            f"FAIL CLOSED: expected {EXPECTED_MONTHLY_BUNDLE_COUNT} symbol records, found {len(records)}"
        )

    details = []
    summaries = {}

    for arm in ARMS:
        exact_deltas = []
        missing_reductions = []
        exact_state_counts = Counter()
        missing_state_counts = Counter()
        joint_state_counts = Counter()
        target_rows = []
        nontarget_rows = []

        for rec in records:
            symbol = rec.get("symbol")
            arms = rec.get("arms") or {}
            native = arms.get("NATIVE_CONTROL") or {}
            trial = arms.get(arm) or {}

            native_exact = int(native.get("exact_frozen_match_count") or 0)
            native_missing = int(native.get("missing_beyond_0_3pct_count") or 0)
            trial_exact = int(trial.get("exact_frozen_match_count") or 0)
            trial_missing = int(trial.get("missing_beyond_0_3pct_count") or 0)

            exact_delta = trial_exact - native_exact
            missing_reduction = native_missing - trial_missing

            exact_state = sign_bucket(exact_delta)
            missing_state = sign_bucket(missing_reduction)
            if exact_delta >= 0 and missing_reduction >= 0 and (exact_delta > 0 or missing_reduction > 0):
                joint = "NON_DEGRADING_IMPROVEMENT"
            elif exact_delta == 0 and missing_reduction == 0:
                joint = "EXACTLY_UNCHANGED"
            elif exact_delta < 0 or missing_reduction < 0:
                joint = "ANY_DEGRADATION"
            else:
                joint = "MIXED_OTHER"

            row = {
                "symbol": symbol,
                "is_target_symbol": symbol in TARGET_SYMBOLS,
                "native_exact": native_exact,
                "trial_exact": trial_exact,
                "exact_delta_vs_native": exact_delta,
                "native_missing": native_missing,
                "trial_missing": trial_missing,
                "missing_reduction_vs_native": missing_reduction,
                "exact_state": exact_state,
                "missing_state": missing_state,
                "joint_state": joint,
            }
            details.append({"arm": arm, **row})
            exact_deltas.append(exact_delta)
            missing_reductions.append(missing_reduction)
            exact_state_counts[exact_state] += 1
            missing_state_counts[missing_state] += 1
            joint_state_counts[joint] += 1
            (target_rows if symbol in TARGET_SYMBOLS else nontarget_rows).append(row)

        def group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "symbol_count": len(rows),
                "exact_delta": describe([r["exact_delta_vs_native"] for r in rows]),
                "missing_reduction": describe([r["missing_reduction_vs_native"] for r in rows]),
                "non_degrading_improvement_count": sum(
                    1 for r in rows if r["joint_state"] == "NON_DEGRADING_IMPROVEMENT"
                ),
                "exactly_unchanged_count": sum(
                    1 for r in rows if r["joint_state"] == "EXACTLY_UNCHANGED"
                ),
                "any_degradation_count": sum(
                    1 for r in rows if r["joint_state"] == "ANY_DEGRADATION"
                ),
            }

        worst_exact = sorted(
            [d for d in details if d["arm"] == arm],
            key=lambda x: (x["exact_delta_vs_native"], x["missing_reduction_vs_native"])
        )[:10]
        worst_missing = sorted(
            [d for d in details if d["arm"] == arm],
            key=lambda x: (x["missing_reduction_vs_native"], x["exact_delta_vs_native"])
        )[:10]
        best_nondegrading = sorted(
            [
                d for d in details
                if d["arm"] == arm and d["joint_state"] == "NON_DEGRADING_IMPROVEMENT"
            ],
            key=lambda x: (x["missing_reduction_vs_native"], x["exact_delta_vs_native"]),
            reverse=True
        )[:10]

        summaries[arm] = {
            "exact_delta_distribution": dict(exact_state_counts),
            "missing_reduction_distribution": dict(missing_state_counts),
            "joint_state_distribution": dict(joint_state_counts),
            "exact_delta_stats": describe(exact_deltas),
            "missing_reduction_stats": describe(missing_reductions),
            "target_symbols": group_stats(target_rows),
            "non_target_symbols": group_stats(nontarget_rows),
            "worst_exact_loss_symbols": worst_exact,
            "worst_missing_increase_symbols": worst_missing,
            "best_non_degrading_symbols": best_nondegrading,
            "globally_non_degrading": (
                all(v >= 0 for v in exact_deltas)
                and all(v >= 0 for v in missing_reductions)
            ),
        }

    split = summaries["OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE"]
    preserve = summaries["OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT"]

    split_widespread = (
        split["joint_state_distribution"].get("ANY_DEGRADATION", 0)
        >= int(EXPECTED_MONTHLY_BUNDLE_COUNT * 0.75)
    )
    preserve_widespread = (
        preserve["joint_state_distribution"].get("ANY_DEGRADATION", 0)
        >= int(EXPECTED_MONTHLY_BUNDLE_COUNT * 0.50)
    )

    if split_widespread:
        conclusion = "SPLIT_WIDE_COLLATERAL_DAMAGE_IS_SYSTEMIC_ACROSS_NON_TARGET_SYMBOLS"
        next_step = "BUILD_M77_19_6_5_2_21_NATIVE_CLUSTER_EVENT_ACTIVATION_DENSITY_FORENSICS"
    elif preserve_widespread:
        conclusion = "PRESERVE_SEED_COLLATERAL_DAMAGE_IS_BROAD_AND_REQUIRES_ACTIVATION_DENSITY_FORENSICS"
        next_step = "BUILD_M77_19_6_5_2_21_NATIVE_CLUSTER_EVENT_ACTIVATION_DENSITY_FORENSICS"
    else:
        conclusion = "COLLATERAL_DAMAGE_IS_CONCENTRATED_AND_REQUIRES_SUBSET_PROVENANCE_FORENSICS"
        next_step = "BUILD_M77_19_6_5_2_21_COLLATERAL_SUBSET_PROVENANCE_FORENSICS"

    report = {
        "version": VERSION,
        "authority_5219": authority,
        "symbol_record_count": len(records),
        "target_symbols": list(TARGET_SYMBOLS),
        "arm_collateral_summaries": summaries,
        "forensic_conclusion": conclusion,
        "candidate_semantic_promoted": False,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": next_step,
        "details": details,
        "governance": {
            "research_only": True,
            "database_mode": "NONE_REPORT_ONLY",
            "production_database_writes": False,
            "new_trigger_semantic_introduced": False,
            "new_threshold_introduced": False,
            "threshold_search_or_optimization": False,
            "symbol_specific_rules_prohibited": True,
            "frozen_target_identity_used_for_triggering": False,
            "historical_answer_leakage": False,
            "candidate_semantic_promoted": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_19_report_sha256": EXPECTED_REPORT_5219_SHA256,
            "m77_19_6_5_2_19_runner_sha256": EXPECTED_RUNNER_5219_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.20 NATIVE OBSERVABLE TRIGGER COLLATERAL IMPACT FORENSICS ===")
    print("database_mode: NONE_REPORT_ONLY")
    print("authority_5219:", authority)
    print("symbol_record_count:", len(records))
    for arm in ARMS:
        s = summaries[arm]
        print(arm, {
            "exact_delta_distribution": s["exact_delta_distribution"],
            "missing_reduction_distribution": s["missing_reduction_distribution"],
            "joint_state_distribution": s["joint_state_distribution"],
            "target_symbols": s["target_symbols"],
            "non_target_symbols": s["non_target_symbols"],
            "globally_non_degrading": s["globally_non_degrading"],
        })
    print("forensic_conclusion:", conclusion)
    print("candidate_semantic_promoted: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", next_step)
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
