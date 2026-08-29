#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median


VERSION = "M77.5-WALK-FORWARD-STABILITY-INCREMENTAL-EDGE-SHADOW-POLICY-1.0"
MODE = "READ_ONLY_POST_WALK_FORWARD_STABILITY_CERTIFICATION"

DEFAULT_INPUT = Path("reports/m77/m77_4_walk_forward_challenger_certification.json")
DEFAULT_OUTPUT = Path("reports/m77/m77_5_shadow_policy_certification.json")
DEFAULT_POLICY = Path("reports/m77/m77_5_research_shadow_policy.json")

# M77.5 intentionally starts only from M77.4's already walk-forward-supported
# candidates. It does not search the rejected candidate space again.
MIN_SELECTED_HOLDOUTS = 2
MIN_FULL_YEAR_HOLDOUTS = 1
MIN_NON_OVERLAPPING_PER_HOLDOUT = 100
MIN_DIRECTIONAL_HIT_RATE_PCT = 50.0
MIN_MATCHED_EXCESS_PCT = 0.0
MIN_THESIS_RETURN_PCT = 0.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_num(v):
    return None if v is None else float(v)


def _candidate_row(item: dict) -> dict:
    folds = list(item.get("folds") or [])
    validations = [f.get("validation") or {} for f in folds]
    full_year = [f for f in folds if f.get("period_status") == "FULL_YEAR"]
    partial_year = [f for f in folds if f.get("period_status") == "PARTIAL_YEAR"]

    returns = [_safe_num(v.get("thesis_return_avg_pct")) for v in validations]
    hits = [_safe_num(v.get("directional_hit_rate_pct")) for v in validations]
    excesses = [
        _safe_num((v.get("matched_control") or {}).get("matched_excess_thesis_return_avg_pct"))
        for v in validations
    ]
    non_overlap = [int(v.get("non_overlapping_observations") or 0) for v in validations]

    returns_n = [v for v in returns if v is not None]
    hits_n = [v for v in hits if v is not None]
    excesses_n = [v for v in excesses if v is not None]

    failure_reasons: list[str] = []
    if int(item.get("selected_holdout_folds") or 0) < MIN_SELECTED_HOLDOUTS:
        failure_reasons.append("INSUFFICIENT_SELECTED_HOLDOUTS")
    if int(item.get("full_year_holdout_folds") or 0) < MIN_FULL_YEAR_HOLDOUTS:
        failure_reasons.append("NO_FULL_YEAR_HOLDOUT_SUPPORT")
    if not bool(item.get("all_selected_holdouts_passed")):
        failure_reasons.append("NOT_ALL_SELECTED_HOLDOUTS_PASSED")
    if non_overlap and min(non_overlap) < MIN_NON_OVERLAPPING_PER_HOLDOUT:
        failure_reasons.append("HOLDOUT_SAMPLE_BELOW_100_NON_OVERLAPPING")
    if returns_n and min(returns_n) <= MIN_THESIS_RETURN_PCT:
        failure_reasons.append("NON_POSITIVE_HOLDOUT_RETURN")
    if hits_n and min(hits_n) < MIN_DIRECTIONAL_HIT_RATE_PCT:
        failure_reasons.append("HOLDOUT_HIT_RATE_BELOW_50")
    if excesses_n and min(excesses_n) <= MIN_MATCHED_EXCESS_PCT:
        failure_reasons.append("NON_POSITIVE_HOLDOUT_MATCHED_EXCESS")

    multi_holdout = int(item.get("selected_holdout_folds") or 0) >= MIN_SELECTED_HOLDOUTS
    full_year_supported = int(item.get("full_year_holdout_folds") or 0) >= MIN_FULL_YEAR_HOLDOUTS
    incremental_edge = bool(excesses_n) and min(excesses_n) > 0.0
    stable_directional = bool(returns_n) and min(returns_n) > 0.0 and bool(hits_n) and min(hits_n) >= 50.0
    breadth_floor = bool(non_overlap) and min(non_overlap) >= MIN_NON_OVERLAPPING_PER_HOLDOUT

    if not failure_reasons:
        status = "SHADOW_POLICY_CERTIFIED"
    elif multi_holdout and full_year_supported and bool(item.get("all_selected_holdouts_passed")):
        status = "WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED"
    else:
        status = "OBSERVATIONAL_WALK_FORWARD_SUPPORT"

    return {
        "candidate_horizon_id": item.get("candidate_horizon_id"),
        "candidate_id": item.get("candidate_id"),
        "dimensions": item.get("dimensions") or {},
        "horizon": item.get("horizon"),
        "selected_holdout_folds": int(item.get("selected_holdout_folds") or 0),
        "full_year_holdout_folds": int(item.get("full_year_holdout_folds") or 0),
        "partial_year_holdout_folds": len(partial_year),
        "passed_holdout_folds": int(item.get("passed_holdout_folds") or 0),
        "all_selected_holdouts_passed": bool(item.get("all_selected_holdouts_passed")),
        "min_non_overlapping_observations": min(non_overlap) if non_overlap else 0,
        "median_non_overlapping_observations": median(non_overlap) if non_overlap else 0,
        "min_thesis_return_pct": min(returns_n) if returns_n else None,
        "median_thesis_return_pct": median(returns_n) if returns_n else None,
        "min_directional_hit_rate_pct": min(hits_n) if hits_n else None,
        "median_directional_hit_rate_pct": median(hits_n) if hits_n else None,
        "min_matched_excess_pct": min(excesses_n) if excesses_n else None,
        "median_matched_excess_pct": median(excesses_n) if excesses_n else None,
        "multi_holdout_stable": multi_holdout,
        "full_year_supported": full_year_supported,
        "incremental_edge_confirmed": incremental_edge,
        "directional_stability_confirmed": stable_directional,
        "sample_floor_confirmed": breadth_floor,
        "status": status,
        "failure_reasons": failure_reasons,
        "holdouts": [
            {
                "validation_year": f.get("validation_year"),
                "period_status": f.get("period_status"),
                "non_overlapping_observations": int((f.get("validation") or {}).get("non_overlapping_observations") or 0),
                "thesis_return_avg_pct": _safe_num((f.get("validation") or {}).get("thesis_return_avg_pct")),
                "directional_hit_rate_pct": _safe_num((f.get("validation") or {}).get("directional_hit_rate_pct")),
                "matched_excess_thesis_return_avg_pct": _safe_num(
                    (((f.get("validation") or {}).get("matched_control") or {}).get("matched_excess_thesis_return_avg_pct"))
                ),
                "passed": bool((f.get("validation") or {}).get("passed")),
            }
            for f in folds
        ],
    }


def build(input_path: Path, output_path: Path, policy_path: Path) -> dict:
    source = json.loads(input_path.read_text())

    governance = source.get("governance") or {}
    if governance.get("production_authority_effect") is not False:
        raise RuntimeError("M77.4 input is not production-authority isolated.")
    if governance.get("research_only") is not True:
        raise RuntimeError("M77.4 input is not explicitly research-only.")
    if governance.get("database_writes") is not False:
        raise RuntimeError("M77.4 input permits database writes; refusing certification.")

    eligible = [
        x for x in (source.get("certification") or [])
        if x.get("research_challenger_eligible") is True
    ]

    rows = [_candidate_row(x) for x in eligible]
    rows.sort(
        key=lambda r: (
            r["status"] != "SHADOW_POLICY_CERTIFIED",
            -(r["selected_holdout_folds"] or 0),
            -(r["full_year_holdout_folds"] or 0),
            -(r["median_matched_excess_pct"] or -9999),
            str(r["candidate_horizon_id"]),
        )
    )

    certified = [r for r in rows if r["status"] == "SHADOW_POLICY_CERTIFIED"]
    supported_not_certified = [
        r for r in rows if r["status"] == "WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED"
    ]
    observational = [r for r in rows if r["status"] == "OBSERVATIONAL_WALK_FORWARD_SUPPORT"]

    full_year_certified = [
        r for r in certified
        if r["full_year_holdout_folds"] >= 2
    ]

    out = {
        "version": VERSION,
        "governance": {
            "mode": MODE,
            "read_only": True,
            "research_only": True,
            "database_writes": False,
            "production_authority_effect": False,
            "production_model_mutation": False,
            "production_threshold_change": False,
            "production_weight_change": False,
            "production_decision_mutation": False,
            "automatic_bearish_inversion": False,
            "automatic_champion_promotion": False,
            "survivorship_bias_free_claim": False,
            "pit_sector_membership_claim": False,
            "partial_year_treated_as_full_year": False,
        },
        "methodology": {
            "input_candidate_scope": "ONLY_M77_4_RESEARCH_CHALLENGER_ELIGIBLE",
            "candidate_search_reopened": False,
            "m77_4_holdout_results_reused_without_relabeling": True,
            "stability_contract": {
                "min_selected_holdouts": MIN_SELECTED_HOLDOUTS,
                "min_full_year_holdouts": MIN_FULL_YEAR_HOLDOUTS,
                "all_selected_holdouts_must_pass": True,
                "min_non_overlapping_observations_each_holdout": MIN_NON_OVERLAPPING_PER_HOLDOUT,
                "min_thesis_return_each_holdout_pct_exclusive": MIN_THESIS_RETURN_PCT,
                "min_directional_hit_rate_each_holdout_pct": MIN_DIRECTIONAL_HIT_RATE_PCT,
                "min_matched_excess_each_holdout_pct_exclusive": MIN_MATCHED_EXCESS_PCT,
            },
            "partial_year_policy": "2026 may contribute supporting evidence but never satisfies the full-year holdout requirement.",
            "promotion_policy": "SHADOW_ONLY_NO_PRODUCTION_PROMOTION",
        },
        "lineage": {
            "m77_4_input": str(input_path),
            "m77_4_sha256": _sha256(input_path),
            "m77_4_version": source.get("challenger_version"),
            "m77_4_regime_authority_version": source.get("regime_authority_version"),
        },
        "coverage": source.get("coverage") or {},
        "summary": {
            "m77_4_research_challenger_eligible": len(eligible),
            "shadow_policy_certified": len(certified),
            "walk_forward_supported_not_shadow_certified": len(supported_not_certified),
            "observational_walk_forward_support": len(observational),
            "certified_with_two_or_more_full_year_holdouts": len(full_year_certified),
            "production_champion_change": False,
        },
        "certification": rows,
    }

    policy = {
        "version": VERSION,
        "mode": "RESEARCH_SHADOW_ONLY",
        "governance": out["governance"],
        "production_champion_change": False,
        "score_mutation": "NONE",
        "threshold_mutation": "NONE",
        "weight_mutation": "NONE",
        "decision_mutation": "NONE",
        "bearish_policy": "ABSTAIN_FROM_BEARISH_CHALLENGER_SUPPORT_DO_NOT_INVERT",
        "partial_year_policy": out["methodology"]["partial_year_policy"],
        "shadow_policy_certified_candidate_horizon_ids": [
            r["candidate_horizon_id"] for r in certified
        ],
        "full_year_depth_preferred_candidate_horizon_ids": [
            r["candidate_horizon_id"] for r in full_year_certified
        ],
        "non_certified_m77_4_supported_candidate_horizon_ids": [
            r["candidate_horizon_id"] for r in rows
            if r["status"] != "SHADOW_POLICY_CERTIFIED"
        ],
        "application_contract": (
            "Research-only annotation. A current bullish baseline observation may be tagged "
            "RESEARCH_SHADOW_POLICY_CERTIFIED only when it matches a listed certified cohort. "
            "This tag must not change production score, direction, strategy, thresholds, weights, "
            "capital allocation, execution, or portfolio-management authority."
        ),
        "lineage": out["lineage"],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n")
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=False) + "\n")

    return {
        "status": "READY",
        "version": VERSION,
        "output": str(output_path),
        "policy_output": str(policy_path),
        **out["summary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--policy-output", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    result = build(Path(args.input), Path(args.output), Path(args.policy_output))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
