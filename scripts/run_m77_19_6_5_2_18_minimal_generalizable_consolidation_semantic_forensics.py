#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.18-MINIMAL-GENERALIZABLE-CONSOLIDATION-SEMANTIC-FORENSICS-1.0"

REPORT_5217_REL = "reports/m77_19_6_5_2_17_minimal_cluster_ancestry_causal_replay.json"
EXPECTED_REPORT_5217_SHA256 = "6b607a5807c380e7dfb0ab12116e3648e4918c12ab17a26648aa45e639e9d5d4"

RUNNER_5217_REL = "scripts/run_m77_19_6_5_2_17_minimal_cluster_ancestry_causal_replay.py"
EXPECTED_RUNNER_5217_SHA256 = "118e8e00ed5c16acfcbfbc8c15f348414b5613002f8cfed2e7eb282100072dde"

LEVEL_REACHABILITY_THRESHOLD = 0.003
PARITY_TOLERANCE = 1e-9
EXPECTED_NATIVE_RECORD_COUNT = 3

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

def validate_5217(report: dict[str, Any]) -> None:
    auth = report.get("authority_5216") or {}
    if auth.get("pass") is not True:
        raise SystemExit("FAIL CLOSED: .2.17 upstream authority not passed")
    if report.get("forensic_conclusion") != "CLUSTER_ANCESTRY_SPLIT_MECHANISMS_CAUSALLY_FALSIFIED_AND_CONFIRMED":
        raise SystemExit("FAIL CLOSED: .2.17 forensic conclusion drift")
    if report.get("candidate_semantic_promoted") is not False:
        raise SystemExit("FAIL CLOSED: .2.17 semantic promotion drift")
    if report.get("combined_arm_forensic_only") is not True:
        raise SystemExit("FAIL CLOSED: .2.17 combined arm governance drift")
    if report.get("production_authority_effect") is not False:
        raise SystemExit("FAIL CLOSED: .2.17 production authority drift")
    if report.get("full_23_year_reconstruction_authorized") is not False:
        raise SystemExit("FAIL CLOSED: .2.17 reconstruction governance drift")

def absorption_predicate(row: dict[str, Any]) -> bool:
    # Identity-free mechanism predicate derived from native trace state:
    # exact target candidate did not seed a new cluster and ends outside native reachability.
    return (
        row.get("target_seeded_new_cluster") is False
        and float(row.get("nearest_relative_distance") or 0.0) >= LEVEL_REACHABILITY_THRESHOLD
    )

def centroid_drift_predicate(row: dict[str, Any]) -> bool:
    # Identity-free mechanism predicate derived from native trace state:
    # exact target candidate seeded a cluster, acquired later members, and final centroid
    # is outside the native reachability threshold.
    return (
        row.get("target_seeded_new_cluster") is True
        and int(row.get("target_cluster_touch_count") or 0) > 1
        and float(row.get("nearest_relative_distance") or 0.0) >= LEVEL_REACHABILITY_THRESHOLD
    )

def classify(row: dict[str, Any]) -> str:
    a = absorption_predicate(row)
    d = centroid_drift_predicate(row)
    if a and d:
        return "AMBIGUOUS"
    if a:
        return "PREEXISTING_CLUSTER_ABSORPTION"
    if d:
        return "POST_SEED_CENTROID_DRIFT"
    return "UNRESOLVED"

def strip_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_seeded_new_cluster": row.get("target_seeded_new_cluster"),
        "target_cluster_touch_count": row.get("target_cluster_touch_count"),
        "nearest_relative_distance": row.get("nearest_relative_distance"),
        "recovered_within_0_3pct": row.get("recovered_within_0_3pct"),
        "target_cluster_final_centroid": row.get("target_cluster_final_centroid"),
        "target_price": row.get("target_price"),
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
        root, REPORT_5217_REL, EXPECTED_REPORT_5217_SHA256, "M77.19.6.5.2.17 report"
    )
    require_file(
        root, RUNNER_5217_REL, EXPECTED_RUNNER_5217_SHA256, "M77.19.6.5.2.17 runner"
    )
    source = load_json(report_path)
    validate_5217(source)

    native_rows = list((source.get("records") or {}).get("NATIVE_TRACE_CONTROL") or [])
    if len(native_rows) != EXPECTED_NATIVE_RECORD_COUNT:
        raise SystemExit(
            f"FAIL CLOSED: expected {EXPECTED_NATIVE_RECORD_COUNT} native causal records, "
            f"observed {len(native_rows)}"
        )

    records = []
    for row in native_rows:
        observed = classify(row)
        expected = {
            "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER": "PREEXISTING_CLUSTER_ABSORPTION",
            "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS": "POST_SEED_CENTROID_DRIFT",
        }.get(row.get("causal_classification"), "UNRESOLVED")

        records.append({
            "symbol": row.get("symbol"),
            "expected_mechanism": expected,
            "identity_free_predicate_mechanism": observed,
            "predicate_match": observed == expected,
            "identity_free_input_projection": strip_identity(row),
            "absorption_predicate": absorption_predicate(row),
            "centroid_drift_predicate": centroid_drift_predicate(row),
        })

    exact_classification_count = sum(1 for r in records if r["predicate_match"])
    ambiguous_count = sum(1 for r in records if r["identity_free_predicate_mechanism"] == "AMBIGUOUS")
    unresolved_count = sum(1 for r in records if r["identity_free_predicate_mechanism"] == "UNRESOLVED")

    # Critical governance distinction:
    # These predicates do NOT use symbol identity, but they still require knowing the frozen
    # target candidate / target cluster ancestry. Therefore they are not yet native-observable
    # production semantics.
    identity_free_mechanism_classification_closed = (
        exact_classification_count == EXPECTED_NATIVE_RECORD_COUNT
        and ambiguous_count == 0
        and unresolved_count == 0
    )
    native_observable_production_generalization_certified = False

    if not identity_free_mechanism_classification_closed:
        raise SystemExit("FAIL CLOSED: identity-free mechanism classification did not close 3/3")

    report = {
        "version": VERSION,
        "authority_5217": {
            "report_sha256": EXPECTED_REPORT_5217_SHA256,
            "runner_sha256": EXPECTED_RUNNER_5217_SHA256,
            "causal_split_confirmed": True,
            "combined_arm_forensic_only": True,
            "candidate_semantic_not_promoted": True,
            "production_authority_unchanged": True,
            "pass": True,
        },
        "native_causal_record_count": len(native_rows),
        "identity_free_predicates": {
            "PREEXISTING_CLUSTER_ABSORPTION": {
                "definition": "target_seeded_new_cluster == false AND nearest_relative_distance >= 0.003",
                "uses_symbol_identity": False,
                "uses_frozen_target_ancestry": True,
            },
            "POST_SEED_CENTROID_DRIFT": {
                "definition": "target_seeded_new_cluster == true AND target_cluster_touch_count > 1 AND nearest_relative_distance >= 0.003",
                "uses_symbol_identity": False,
                "uses_frozen_target_ancestry": True,
            },
        },
        "records": records,
        "classification_summary": {
            "exact_classification_count": exact_classification_count,
            "ambiguous_count": ambiguous_count,
            "unresolved_count": unresolved_count,
            "identity_free_mechanism_classification_closed": identity_free_mechanism_classification_closed,
        },
        "forensic_conclusion": "SYMBOL_IDENTITY_FREE_MECHANISM_PREDICATES_CLOSE_3_OF_3_BUT_REQUIRE_FROZEN_TARGET_ANCESTRY",
        "generalization_assessment": {
            "symbol_identity_free": True,
            "mechanism_specific": True,
            "frozen_target_ancestry_required": True,
            "native_observable_only": False,
            "production_generalizable_semantic_certified": False,
            "reason": "A production rule cannot depend on knowing which native candidate should match a frozen historical target.",
        },
        "candidate_semantic_promoted": False,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": "BUILD_M77_19_6_5_2_19_NATIVE_OBSERVABLE_CONSOLIDATION_TRIGGER_CAUSAL_REPLAY",
        "governance": {
            "research_only": True,
            "database_mode": "NONE_REPORT_ONLY",
            "production_database_writes": False,
            "symbol_specific_rules_prohibited": True,
            "target_specific_rules_prohibited_for_promotion": True,
            "threshold_search_or_optimization": False,
            "native_level_merge_threshold": LEVEL_REACHABILITY_THRESHOLD,
            "native_level_merge_threshold_relaxed": False,
            "parity_thresholds_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "candidate_semantic_promoted": False,
            "native_observable_production_generalization_certified": native_observable_production_generalization_certified,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.18 MINIMAL GENERALIZABLE CONSOLIDATION SEMANTIC FORENSICS ===")
    print("database_mode: NONE_REPORT_ONLY")
    print("authority_5217:", report["authority_5217"])
    print("native_causal_record_count:", len(native_rows))
    print("classification_summary:", report["classification_summary"])
    for rec in records:
        print(
            rec["symbol"],
            rec["expected_mechanism"],
            "=>",
            rec["identity_free_predicate_mechanism"],
            "match=",
            rec["predicate_match"],
        )
    print("forensic_conclusion:", report["forensic_conclusion"])
    print("symbol_identity_free: True")
    print("frozen_target_ancestry_required: True")
    print("native_observable_only: False")
    print("production_generalizable_semantic_certified: False")
    print("candidate_semantic_promoted: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
