#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

VERSION = "M77.19.6.5.2.22-NATIVE-EVENT-STATE-DISCRIMINATOR-FORENSICS-1.0"

REPORT_5221_REL = "reports/m77_19_6_5_2_21_native_cluster_event_activation_density_forensics.json"
EXPECTED_REPORT_5221_SHA256 = "13ca75225a523cd7993e990af495734bc1ea0ca559f575119a031fe57122fb44"

RUNNER_5221_REL = "scripts/run_m77_19_6_5_2_21_native_cluster_event_activation_density_forensics.py"
EXPECTED_RUNNER_5221_SHA256 = "c7fd0c6e1773cc367653f1cd56a5a277c2d50056fd3b73ff92b7fec09a5dbe79"

EXPECTED_EVENT_COUNT = 4991
EXPECTED_CAUSAL_LABELS = ("AES_RESISTANCE", "ANET_SUPPORT", "ATO_RESISTANCE")

NUMERIC_FIELDS = (
    "seq",
    "cluster_count_before",
    "atr",
    "native_merge_distance_abs",
    "eligible_cluster_count",
    "selected_cluster_touch_count_before",
    "candidate_gap_rel_to_centroid",
    "centroid_drift_from_seed_before",
    "centroid_drift_from_seed_after",
)

CATEGORICAL_FIELDS = (
    "native_action",
    "timeframe",
    "side",
    "candidate_source",
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

def validate_5221(report: dict[str, Any]) -> dict[str, Any]:
    split = ((report.get("activation_density") or {})
             .get("OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE") or {})
    preserve = ((report.get("activation_density") or {})
                .get("OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT") or {})
    labels = tuple(x.get("label") for x in (report.get("causal_event_projection") or []))
    checks = {
        "event_count_4991": report.get("total_raw_candidate_event_count") == EXPECTED_EVENT_COUNT,
        "split_dense_1742": split.get("activation_count") == 1742,
        "split_symbols_48": split.get("symbols_with_activation_count") == 48,
        "preserve_dense_636": preserve.get("activation_count") == 636,
        "preserve_symbols_47": preserve.get("symbols_with_activation_count") == 47,
        "causal_labels_exact": labels == EXPECTED_CAUSAL_LABELS,
        "forensic_conclusion": report.get("forensic_conclusion")
            == "EXISTING_OBSERVABLE_TRIGGERS_ACTIVATE_DENSELY_ACROSS_NATIVE_CLUSTER_EVENTS",
        "semantic_not_promoted": report.get("candidate_semantic_promoted") is False,
        "new_trigger_false": report.get("new_trigger_semantic_introduced") is False,
        "new_threshold_false": report.get("new_threshold_introduced") is False,
        "parity_not_certified": report.get("controlled_exact_input_parity_certified") is False,
        "reconstruction_blocked": report.get("full_23_year_reconstruction_authorized") is False,
        "production_unchanged": report.get("production_authority_effect") is False,
    }
    checks["pass"] = all(checks.values())
    if not checks["pass"]:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.21 authority validation failed: {checks}")
    return checks

def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }

def empirical_rank(values: list[float], target: float) -> dict[str, Any]:
    if not values:
        return {
            "comparable_count": 0,
            "less_count": 0,
            "equal_count": 0,
            "greater_count": 0,
            "percentile_less_or_equal": None,
            "percentile_midrank": None,
            "edge_proximity": None,
        }
    less = sum(v < target for v in values)
    equal = sum(v == target for v in values)
    greater = len(values) - less - equal
    ple = (less + equal) / len(values)
    mid = (less + 0.5 * equal) / len(values)
    return {
        "comparable_count": len(values),
        "less_count": less,
        "equal_count": equal,
        "greater_count": greater,
        "percentile_less_or_equal": ple,
        "percentile_midrank": mid,
        "edge_proximity": min(mid, 1.0 - mid),
    }

def action_background(events: list[dict[str, Any]], causal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e for e in events
        if e.get("causal_target_label") is None
        and e.get("native_action") == causal.get("native_action")
    ]

def conditioned_background(
    events: list[dict[str, Any]],
    causal: dict[str, Any],
    condition_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [
        e for e in events
        if e.get("causal_target_label") is None
        and all(e.get(k) == causal.get(k) for k in condition_fields)
    ]

def categorical_support(
    background: list[dict[str, Any]],
    causal: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    exact = sum(all(e.get(k) == causal.get(k) for k in fields) for e in background)
    return {
        "fields": list(fields),
        "background_count": len(background),
        "exact_match_count": exact,
        "exact_match_rate": exact / len(background) if background else None,
    }

def numeric_projection(
    background: list[dict[str, Any]],
    causal: dict[str, Any],
) -> dict[str, Any]:
    out = {}
    for field in NUMERIC_FIELDS:
        target = causal.get(field)
        if not finite_number(target):
            out[field] = {
                "causal_value": target,
                "background_distribution": describe([]),
                "empirical_rank": empirical_rank([], 0.0),
                "status": "NOT_COMPARABLE_NULL_CAUSAL_VALUE",
            }
            continue
        vals = [
            float(e[field]) for e in background
            if finite_number(e.get(field))
        ]
        out[field] = {
            "causal_value": float(target),
            "background_distribution": describe(vals),
            "empirical_rank": empirical_rank(vals, float(target)),
            "status": "COMPARABLE" if vals else "NO_BACKGROUND_VALUES",
        }
    return out

def rank_map(values: list[float], target: float) -> float | None:
    r = empirical_rank(values, target).get("percentile_midrank")
    return float(r) if r is not None else None

def nearest_neighbors(
    background: list[dict[str, Any]],
    causal: dict[str, Any],
    limit: int = 12,
) -> list[dict[str, Any]]:
    # Diagnostic only: fixed rank-space L1 distance over available native numeric observables.
    # No cutoff, fitting, weighting search, or classifier is used.
    pools = {}
    for field in NUMERIC_FIELDS:
        pools[field] = [
            float(e[field]) for e in background if finite_number(e.get(field))
        ]

    target_ranks = {}
    for field in NUMERIC_FIELDS:
        if finite_number(causal.get(field)) and pools[field]:
            target_ranks[field] = rank_map(pools[field], float(causal[field]))

    scored = []
    for e in background:
        diffs = []
        used = []
        for field, tr in target_ranks.items():
            if not finite_number(e.get(field)):
                continue
            er = rank_map(pools[field], float(e[field]))
            if er is None:
                continue
            diffs.append(abs(er - tr))
            used.append(field)

        categorical_mismatch = sum(
            e.get(k) != causal.get(k)
            for k in ("timeframe", "side", "candidate_source")
        )
        # Each categorical mismatch contributes one full rank-space unit.
        distance = (sum(diffs) + float(categorical_mismatch)) / max(1, len(diffs) + 3)
        scored.append((distance, e, used, categorical_mismatch))

    scored.sort(key=lambda x: (x[0], str(x[1].get("symbol")), int(x[1].get("seq") or 0)))
    out = []
    for distance, e, used, mismatch in scored[:limit]:
        out.append({
            "rank_space_l1_distance": distance,
            "numeric_fields_used": used,
            "categorical_mismatch_count": mismatch,
            "symbol": e.get("symbol"),
            "timeframe": e.get("timeframe"),
            "side": e.get("side"),
            "candidate_source": e.get("candidate_source"),
            "native_action": e.get("native_action"),
            "seq": e.get("seq"),
            "cluster_count_before": e.get("cluster_count_before"),
            "eligible_cluster_count": e.get("eligible_cluster_count"),
            "selected_cluster_touch_count_before": e.get("selected_cluster_touch_count_before"),
            "candidate_gap_rel_to_centroid": e.get("candidate_gap_rel_to_centroid"),
            "centroid_drift_from_seed_before": e.get("centroid_drift_from_seed_before"),
            "centroid_drift_from_seed_after": e.get("centroid_drift_from_seed_after"),
            "atr": e.get("atr"),
            "native_merge_distance_abs": e.get("native_merge_distance_abs"),
        })
    return out

def summarize_causal(events: list[dict[str, Any]], causal: dict[str, Any]) -> dict[str, Any]:
    action_bg = action_background(events, causal)
    same_tf_bg = conditioned_background(
        events, causal, ("native_action", "timeframe")
    )
    same_tf_side_source_bg = conditioned_background(
        events, causal, ("native_action", "timeframe", "side", "candidate_source")
    )

    supports = {
        "action_only": categorical_support(
            action_bg, causal, ("native_action",)
        ),
        "action_timeframe": categorical_support(
            action_bg, causal, ("native_action", "timeframe")
        ),
        "action_timeframe_side": categorical_support(
            action_bg, causal, ("native_action", "timeframe", "side")
        ),
        "action_timeframe_side_source": categorical_support(
            action_bg, causal, ("native_action", "timeframe", "side", "candidate_source")
        ),
    }

    return {
        "label": causal.get("causal_target_label"),
        "symbol": causal.get("symbol"),
        "native_action": causal.get("native_action"),
        "timeframe": causal.get("timeframe"),
        "side": causal.get("side"),
        "candidate_source": causal.get("candidate_source"),
        "causal_state": {
            k: causal.get(k)
            for k in (
                "seq",
                "cluster_count_before",
                "eligible_cluster_count",
                "selected_cluster_touch_count_before",
                "candidate_gap_rel_to_centroid",
                "centroid_drift_from_seed_before",
                "centroid_drift_from_seed_after",
                "atr",
                "native_merge_distance_abs",
            )
        },
        "categorical_support": supports,
        "numeric_projection_action_conditioned": numeric_projection(action_bg, causal),
        "numeric_projection_action_timeframe_conditioned": numeric_projection(same_tf_bg, causal),
        "numeric_projection_action_timeframe_side_source_conditioned": numeric_projection(
            same_tf_side_source_bg, causal
        ),
        "nearest_action_conditioned_native_neighbors": nearest_neighbors(
            action_bg, causal, 12
        ),
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
        root, REPORT_5221_REL, EXPECTED_REPORT_5221_SHA256,
        "M77.19.6.5.2.21 report",
    )
    require_file(
        root, RUNNER_5221_REL, EXPECTED_RUNNER_5221_SHA256,
        "M77.19.6.5.2.21 runner",
    )

    source = load_json(report_path)
    authority = validate_5221(source)
    events = source.get("events") or []
    if len(events) != EXPECTED_EVENT_COUNT:
        raise SystemExit(
            f"FAIL CLOSED: expected {EXPECTED_EVENT_COUNT} events, found {len(events)}"
        )

    causal_events = [
        e for e in events if e.get("causal_target_label") in EXPECTED_CAUSAL_LABELS
    ]
    by_label = {e["causal_target_label"]: e for e in causal_events}
    if tuple(by_label.keys()) != EXPECTED_CAUSAL_LABELS:
        # Preserve deterministic expected order.
        causal_events = [by_label.get(label) for label in EXPECTED_CAUSAL_LABELS]
    if any(e is None for e in causal_events):
        raise SystemExit("FAIL CLOSED: one or more exact causal events missing")

    projections = [summarize_causal(events, e) for e in causal_events]

    action_distribution = Counter(e.get("native_action") for e in events)
    source_distribution = Counter(e.get("candidate_source") for e in events)
    timeframe_distribution = Counter(e.get("timeframe") for e in events)

    report = {
        "version": VERSION,
        "authority_5221": authority,
        "event_count": len(events),
        "population_context": {
            "native_action_distribution": dict(action_distribution),
            "candidate_source_distribution": dict(source_distribution),
            "timeframe_distribution": dict(timeframe_distribution),
        },
        "causal_state_discriminator_projections": projections,
        "forensic_conclusion": "CAUSAL_EVENTS_OCCUPY_HETEROGENEOUS_NATIVE_ACTION_STATES_REQUIRING_ACTION_CONDITIONED_DIAGNOSTICS",
        "classifier_trained": False,
        "decision_boundary_fitted": False,
        "new_trigger_semantic_introduced": False,
        "new_threshold_introduced": False,
        "threshold_search_or_optimization": False,
        "candidate_semantic_promoted": False,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": "BUILD_M77_19_6_5_2_23_CAUSAL_STATE_NEIGHBORHOOD_COLLATERAL_FORENSICS",
        "governance": {
            "research_only": True,
            "database_mode": "NONE_REPORT_ONLY",
            "production_database_writes": False,
            "source_event_stream_reused_exactly": True,
            "causal_identity_used_for_diagnostic_projection_only": True,
            "causal_identity_used_for_rule_construction": False,
            "symbol_identity_used_in_trigger_logic": False,
            "historical_answer_leakage_into_trigger_logic": False,
            "classifier_trained": False,
            "decision_boundary_fitted": False,
            "feature_weight_optimization": False,
            "neighbor_cutoff_selected": False,
            "threshold_search_or_optimization": False,
            "new_trigger_semantic_introduced": False,
            "new_threshold_introduced": False,
            "candidate_semantic_promoted": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "source_authorities": {
            "m77_19_6_5_2_21_report_sha256": EXPECTED_REPORT_5221_SHA256,
            "m77_19_6_5_2_21_runner_sha256": EXPECTED_RUNNER_5221_SHA256,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.5.2.22 NATIVE EVENT STATE DISCRIMINATOR FORENSICS ===")
    print("database_mode: NONE_REPORT_ONLY")
    print("authority_5221:", authority)
    print("event_count:", len(events))
    print("population_context:", report["population_context"])
    for p in projections:
        print()
        print(p["label"], {
            "native_action": p["native_action"],
            "timeframe": p["timeframe"],
            "side": p["side"],
            "candidate_source": p["candidate_source"],
            "causal_state": p["causal_state"],
            "categorical_support": p["categorical_support"],
            "numeric_projection_action_timeframe_side_source_conditioned":
                p["numeric_projection_action_timeframe_side_source_conditioned"],
            "nearest_action_conditioned_native_neighbors":
                p["nearest_action_conditioned_native_neighbors"][:5],
        })
    print()
    print("forensic_conclusion:", report["forensic_conclusion"])
    print("classifier_trained: False")
    print("decision_boundary_fitted: False")
    print("new_trigger_semantic_introduced: False")
    print("new_threshold_introduced: False")
    print("candidate_semantic_promoted: False")
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:", report["next_step"])
    print("report:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
