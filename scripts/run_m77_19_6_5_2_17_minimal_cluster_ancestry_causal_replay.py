#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.2.17-MINIMAL-CLUSTER-ANCESTRY-CAUSAL-REPLAY-1.0"

REPORT_5216_REL = "reports/m77_19_6_5_2_16_target_cluster_ancestry_provenance_trace.json"
EXPECTED_REPORT_5216_SHA256 = "14d27a0b77de03c306baa76f4b1178201f97305612f32f84e9c97ce2b8c41752"

RUNNER_5216_REL = "scripts/run_m77_19_6_5_2_16_target_cluster_ancestry_provenance_trace.py"
EXPECTED_RUNNER_5216_SHA256 = "870593692bdb5532bac463606c0715726a2667431d6fd699adf7bd8c9b21d762"

PARITY_TOLERANCE = 1e-9
LEVEL_REACHABILITY_THRESHOLD = 0.003
NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35
EXPECTED_TARGET_COUNT = 3

EXPECTED_CLASSES = {
    "AES": "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER",
    "ANET": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS",
    "ATO": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS",
}

ARMS = (
    "NATIVE_TRACE_CONTROL",
    "ABSORPTION_ONLY_FORCE_TARGET_NEW_CLUSTER",
    "CENTROID_DRIFT_ONLY_PIN_TARGET_CLUSTER",
    "COMBINED_MINIMAL_TARGET_LOCAL",
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

def validate_5216(report: dict[str, Any]) -> None:
    if report.get("target_count") != EXPECTED_TARGET_COUNT:
        raise SystemExit("FAIL CLOSED: .2.16 target_count drift")
    if report.get("candidate_semantic_promoted") is not False:
        raise SystemExit("FAIL CLOSED: .2.16 candidate semantic promotion drift")
    if report.get("keep_seed_price_globally_rejected") is not True:
        raise SystemExit("FAIL CLOSED: KEEP_SEED_PRICE rejection drift")
    if report.get("production_authority_effect") is not False:
        raise SystemExit("FAIL CLOSED: production authority drift")
    seen = {r["symbol"]: r["trace"]["causal_classification"] for r in report.get("records") or []}
    if seen != EXPECTED_CLASSES:
        raise SystemExit(f"FAIL CLOSED: .2.16 causal classification drift: {seen}")

def target_event(record: dict[str, Any]) -> dict[str, Any]:
    events = record["trace"]["event_trace"]
    matches = [e for e in events if e.get("is_exact_target_candidate")]
    if len(matches) != 1:
        raise SystemExit(f"FAIL CLOSED: expected exactly one target event for {record['symbol']}")
    return matches[0]

def replay_record(record: dict[str, Any], arm: str) -> dict[str, Any]:
    target = record["target"]
    target_price = float(target["price"])
    target_type = "SUPPORT" if str(target["side"]).lower() == "support" else "RESISTANCE"
    merge_distance = float(record["merge_distance"])
    causal_class = record["trace"]["causal_classification"]
    target_seq = int(target_event(record)["seq"])

    clusters: list[dict[str, Any]] = []
    target_cluster_id = None
    target_seeded_new = False
    intervention_events = []

    for e0 in record["trace"]["event_trace"]:
        e = deepcopy(e0)
        price = float(e["price"])
        typ = e["type"]

        eligible = []
        for ci, c in enumerate(clusters):
            if c["type"] != typ:
                continue
            d = abs(float(c["centroid"]) - price)
            if d <= merge_distance:
                eligible.append((ci, d))

        is_target = int(e["seq"]) == target_seq and typ == target_type and abs(price - target_price) <= PARITY_TOLERANCE

        force_new = (
            arm in ("ABSORPTION_ONLY_FORCE_TARGET_NEW_CLUSTER", "COMBINED_MINIMAL_TARGET_LOCAL")
            and causal_class == "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER"
            and is_target
        )

        if eligible and not force_new:
            ci, _ = eligible[0]
            c = clusters[ci]
            before = float(c["centroid"])

            pin_target_cluster = (
                arm in ("CENTROID_DRIFT_ONLY_PIN_TARGET_CLUSTER", "COMBINED_MINIMAL_TARGET_LOCAL")
                and causal_class == "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"
                and target_cluster_id is not None
                and ci == target_cluster_id
            )

            if pin_target_cluster:
                after = float(c["centroid"])
                c["touch_count"] += 1
                c["members"].append(dict(e))
                intervention_events.append({
                    "seq": e["seq"],
                    "intervention": "PIN_TARGET_CLUSTER_CENTROID",
                    "centroid_before": before,
                    "incoming_price": price,
                    "centroid_after": after,
                })
            else:
                c["centroid"] = (
                    c["centroid"] * c["touch_count"] + price
                ) / (c["touch_count"] + 1)
                c["touch_count"] += 1
                c["members"].append(dict(e))

            if is_target and target_cluster_id is None:
                target_cluster_id = ci
                target_seeded_new = False
        else:
            ci = len(clusters)
            clusters.append({
                "id": ci,
                "type": typ,
                "seed_price": price,
                "centroid": price,
                "touch_count": 1,
                "members": [dict(e)],
            })
            if is_target:
                target_cluster_id = ci
                target_seeded_new = True
                if force_new:
                    intervention_events.append({
                        "seq": e["seq"],
                        "intervention": "FORCE_ABSORBED_TARGET_TO_NEW_CLUSTER",
                        "target_price": target_price,
                        "eligible_native_cluster_count": len(eligible),
                        "eligible_native_cluster_ids": [x[0] for x in eligible],
                    })

    same_side = [c for c in clusters if c["type"] == target_type]
    nearest = min(
        (abs(float(c["centroid"]) - target_price) / max(1.0, abs(target_price)), c)
        for c in same_side
    )
    recovered = nearest[0] < LEVEL_REACHABILITY_THRESHOLD

    target_cluster = clusters[target_cluster_id] if target_cluster_id is not None else None

    return {
        "arm": arm,
        "symbol": record["symbol"],
        "target_price": target_price,
        "causal_classification": causal_class,
        "target_seeded_new_cluster": target_seeded_new,
        "target_cluster_id": target_cluster_id,
        "target_cluster_final_centroid": (
            float(target_cluster["centroid"]) if target_cluster is not None else None
        ),
        "target_cluster_touch_count": (
            int(target_cluster["touch_count"]) if target_cluster is not None else None
        ),
        "nearest_relative_distance": float(nearest[0]),
        "recovered_within_0_3pct": bool(recovered),
        "intervention_events": intervention_events,
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

    report_path = require_file(root, REPORT_5216_REL, EXPECTED_REPORT_5216_SHA256, "M77.19.6.5.2.16 report")
    require_file(root, RUNNER_5216_REL, EXPECTED_RUNNER_5216_SHA256, "M77.19.6.5.2.16 runner")
    report5216 = load_json(report_path)
    validate_5216(report5216)

    records = report5216["records"]
    results = {arm: [] for arm in ARMS}
    for arm in ARMS:
        for rec in records:
            results[arm].append(replay_record(rec, arm))

    summaries = {}
    for arm, rows in results.items():
        recovered_symbols = [r["symbol"] for r in rows if r["recovered_within_0_3pct"]]
        summaries[arm] = {
            "recovered_count": len(recovered_symbols),
            "recovered_symbols": recovered_symbols,
        }

    expected = {
        "NATIVE_TRACE_CONTROL": [],
        "ABSORPTION_ONLY_FORCE_TARGET_NEW_CLUSTER": ["AES"],
        "CENTROID_DRIFT_ONLY_PIN_TARGET_CLUSTER": ["ANET", "ATO"],
        "COMBINED_MINIMAL_TARGET_LOCAL": ["AES", "ANET", "ATO"],
    }
    for arm, symbols in expected.items():
        if summaries[arm]["recovered_symbols"] != symbols:
            raise SystemExit(
                f"FAIL CLOSED: mechanism falsification failed for {arm} "
                f"expected={symbols} actual={summaries[arm]['recovered_symbols']}"
            )

    report = {
        "version": VERSION,
        "authority_5216": {
            "report_sha256": EXPECTED_REPORT_5216_SHA256,
            "runner_sha256": EXPECTED_RUNNER_5216_SHA256,
            "target_count_3": True,
            "classification_split_exact": True,
            "keep_seed_price_globally_rejected": True,
            "production_authority_unchanged": True,
            "pass": True,
        },
        "arms": list(ARMS),
        "arm_summaries": summaries,
        "records": results,
        "forensic_conclusion": "CLUSTER_ANCESTRY_SPLIT_MECHANISMS_CAUSALLY_FALSIFIED_AND_CONFIRMED",
        "mechanism_map": {
            "AES": "PREEXISTING_CLUSTER_ABSORPTION",
            "ANET": "POST_SEED_CENTROID_DRIFT",
            "ATO": "POST_SEED_CENTROID_DRIFT",
        },
        "candidate_semantic_promoted": False,
        "combined_arm_forensic_only": True,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": "BUILD_M77_19_6_5_2_18_MINIMAL_GENERALIZABLE_CONSOLIDATION_SEMANTIC_FORENSICS",
        "governance": {
            "research_only": True,
            "database_mode": "NONE_REPORT_ONLY",
            "production_database_writes": False,
            "native_candidate_generation_unchanged": True,
            "native_internal_atr_merge_multiplier": NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER,
            "native_internal_atr_merge_multiplier_relaxed": False,
            "native_level_merge_threshold": LEVEL_REACHABILITY_THRESHOLD,
            "native_level_merge_threshold_relaxed": False,
            "parity_thresholds_relaxed": False,
            "parity_tolerance": PARITY_TOLERANCE,
            "threshold_search_or_optimization": False,
            "target_local_interventions_only": True,
            "global_semantic_inference_authorized": False,
            "production_authority_effect": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.17 MINIMAL CLUSTER ANCESTRY CAUSAL REPLAY ===")
    print("database_mode: NONE_REPORT_ONLY")
    print("authority_5216:", report["authority_5216"])
    for arm in ARMS:
        print(arm, summaries[arm])
    print("mechanism_map:", report["mechanism_map"])
    print("forensic_conclusion:", report["forensic_conclusion"])
    print("candidate_semantic_promoted: False")
    print("combined_arm_forensic_only: True")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
