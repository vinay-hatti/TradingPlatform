#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

VERSION = "CYCLICAL-SEASONALITY-WALK-FORWARD-CERTIFICATION-1.0"

DEFAULT_INPUT = Path(
    "reports/cyclical_seasonality/cyclical_seasonality_research_audit.json"
)
DEFAULT_OUTPUT = Path(
    "reports/cyclical_seasonality/"
    "cyclical_seasonality_walk_forward_certification.json"
)
DEFAULT_POLICY = Path(
    "reports/cyclical_seasonality/"
    "cyclical_seasonality_shadow_candidate_policy.json"
)

HORIZONS = (20, 60)

# Research-certification gates only. These are not production thresholds.
MIN_HOLDOUT_NONOVERLAP_N = 100
MIN_SELECTED_HOLDOUTS = 2
MIN_FULL_YEAR_HOLDOUTS = 1
MIN_HOLDOUT_THESIS_RETURN_PCT = 0.0
MIN_HOLDOUT_HIT_RATE_PCT = 50.0
MIN_MATCHED_EXCESS_BY_HORIZON = {20: 0.25, 60: 0.50}
MAX_DEGRADATION_FRACTION = 0.50

# Expanding-window folds. 2026 remains partial-year supporting evidence.
FOLDS = (
    {"holdout_year": 2023, "credit": "FULL_YEAR"},
    {"holdout_year": 2024, "credit": "FULL_YEAR"},
    {"holdout_year": 2025, "credit": "FULL_YEAR"},
    {"holdout_year": 2026, "credit": "PARTIAL_YEAR"},
)


def load(path: Path):
    return json.loads(path.read_text())


def stable_key(e):
    return (
        e["factor_family"],
        e["factor"],
        e["state"],
        e["direction"],
        int(e["horizon"]),
    )


def q75_positive(yearly):
    if not yearly:
        return False
    p = sum(1 for y in yearly if y.get("thesis_return_avg_pct", 0) > 0)
    return 100.0 * p / len(yearly) >= 75.0


def training_eligible(e, training_years):
    """
    Selection uses only evidence available before the holdout year.
    The full-sample 1.1 research_screen is NOT used here as a holdout selector.
    """
    yearly = [
        y for y in (e.get("yearly") or [])
        if int(y["year"]) in training_years
    ]
    if len(yearly) < 2:
        return False, ["TRAINING_YEARS_BELOW_2"]

    reasons = []
    if not q75_positive(yearly):
        reasons.append("TRAINING_POSITIVE_YEAR_RATE_BELOW_75")
    if mean(y["thesis_return_avg_pct"] for y in yearly) <= 0:
        reasons.append("TRAINING_THESIS_RETURN_NONPOSITIVE")

    # The full-sample matched excess cannot be used for holdout selection.
    # Require only directionally persistent pre-holdout yearly evidence here.
    return (not reasons), reasons


def holdout_row(e, holdout_year):
    yearly = [
        y for y in (e.get("yearly") or [])
        if int(y["year"]) == int(holdout_year)
    ]
    if not yearly:
        return None

    y = yearly[0]
    # 1.1 yearly records are already based on deterministic non-overlap cohorts.
    # The audit's matched-control excess is full-sample, so we DO NOT leak it
    # into holdout certification. We use year-specific absolute thesis evidence,
    # and retain full-sample matched excess only as lineage/reference metadata.
    return {
        "year": int(holdout_year),
        "observations": int(y.get("observations", 0)),
        "raw_underlying_return_avg_pct": y.get(
            "raw_underlying_return_avg_pct"
        ),
        "thesis_return_avg_pct": y.get("thesis_return_avg_pct"),
        "directional_hit_rate_pct": y.get("directional_hit_rate_pct"),
    }


def fold_pass(e, row):
    reasons = []
    h = int(e["horizon"])
    if row["observations"] < MIN_HOLDOUT_NONOVERLAP_N:
        reasons.append("HOLDOUT_NONOVERLAP_SAMPLE_BELOW_100")
    if (
        row["thesis_return_avg_pct"] is None
        or row["thesis_return_avg_pct"] <= MIN_HOLDOUT_THESIS_RETURN_PCT
    ):
        reasons.append("HOLDOUT_THESIS_RETURN_NONPOSITIVE")
    if (
        row["directional_hit_rate_pct"] is None
        or row["directional_hit_rate_pct"] < MIN_HOLDOUT_HIT_RATE_PCT
    ):
        reasons.append("HOLDOUT_DIRECTIONAL_HIT_BELOW_50")

    ref_excess = (
        (e.get("matched_control") or {})
        .get("matched_excess_thesis_return_avg_pct")
    )
    ref_floor = MIN_MATCHED_EXCESS_BY_HORIZON[h]
    # This is a reference-only diagnostic. It cannot rescue a failing holdout.
    excess_reference_ok = (
        ref_excess is not None and float(ref_excess) >= ref_floor
    )

    return {
        "passed": not reasons,
        "reasons": reasons,
        "full_sample_matched_excess_reference_pct": ref_excess,
        "full_sample_reference_effect_floor_pct": ref_floor,
        "full_sample_reference_effect_floor_pass": excess_reference_ok,
    }


def aliases(audit):
    aliased = set()
    for x in (
        (audit.get("alias_diagnostics") or {})
        .get("aliased_factor_states", [])
    ):
        aliased.add((x["factor"], x["state"]))
    return aliased


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--policy-output", default=str(DEFAULT_POLICY))
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    policy_out = Path(args.policy_output)

    if not inp.exists():
        raise SystemExit(f"Missing hardened 1.1 audit: {inp}")

    audit = load(inp)
    if audit.get("version") != "CYCLICAL-SEASONALITY-RESEARCH-AUDIT-1.1":
        raise SystemExit(
            "Walk-forward requires CYCLICAL-SEASONALITY-RESEARCH-AUDIT-1.1"
        )

    aliased = aliases(audit)

    # Candidate universe may include all 1.1 evidence rows, but each fold
    # performs its own training-only selection.
    evidence = [
        e for e in audit.get("evidence", [])
        if e["factor"] != "weekday"
        and (e["factor"], e["state"]) not in aliased
    ]

    fold_reports = []
    histories = defaultdict(list)

    for fold in FOLDS:
        holdout = int(fold["holdout_year"])
        training_years = sorted(
            {
                int(y["year"])
                for e in evidence
                for y in (e.get("yearly") or [])
                if int(y["year"]) < holdout
            }
        )

        selected = passed = failed = 0
        records = []

        for e in evidence:
            ok, selection_reasons = training_eligible(e, training_years)
            if not ok:
                continue

            row = holdout_row(e, holdout)
            if row is None:
                continue

            selected += 1
            verdict = fold_pass(e, row)
            if verdict["passed"]:
                passed += 1
            else:
                failed += 1

            rec = {
                "factor_family": e["factor_family"],
                "factor": e["factor"],
                "state": e["state"],
                "direction": e["direction"],
                "horizon": int(e["horizon"]),
                "training_years": training_years,
                "selection_reasons": selection_reasons,
                "holdout_credit": fold["credit"],
                "holdout": row,
                "verdict": verdict,
            }
            records.append(rec)
            histories[stable_key(e)].append(rec)

        fold_reports.append(
            {
                "holdout_year": holdout,
                "holdout_credit": fold["credit"],
                "training_years": training_years,
                "selected": selected,
                "passed": passed,
                "failed": failed,
                "records": records,
            }
        )

    supported = []
    for key, recs in sorted(histories.items()):
        selected_holdouts = len(recs)
        passed_holdouts = sum(r["verdict"]["passed"] for r in recs)
        full_year = sum(
            r["holdout_credit"] == "FULL_YEAR" for r in recs
        )
        full_year_passed = sum(
            r["holdout_credit"] == "FULL_YEAR"
            and r["verdict"]["passed"]
            for r in recs
        )

        passed_rows = [r for r in recs if r["verdict"]["passed"]]
        worst_return = (
            min(r["holdout"]["thesis_return_avg_pct"] for r in passed_rows)
            if passed_rows else None
        )
        worst_hit = (
            min(r["holdout"]["directional_hit_rate_pct"] for r in passed_rows)
            if passed_rows else None
        )
        min_n = (
            min(r["holdout"]["observations"] for r in passed_rows)
            if passed_rows else 0
        )

        # Stability requirement:
        # - at least 2 selected holdouts,
        # - at least one full-year holdout,
        # - every selected holdout must pass.
        reasons = []
        if selected_holdouts < MIN_SELECTED_HOLDOUTS:
            reasons.append("SELECTED_HOLDOUTS_BELOW_2")
        if full_year < MIN_FULL_YEAR_HOLDOUTS:
            reasons.append("FULL_YEAR_HOLDOUTS_BELOW_1")
        if passed_holdouts != selected_holdouts:
            reasons.append("ONE_OR_MORE_SELECTED_HOLDOUTS_FAILED")

        # Degradation diagnostic versus the first passed full-year result.
        full_pass = [
            r for r in recs
            if r["holdout_credit"] == "FULL_YEAR"
            and r["verdict"]["passed"]
        ]
        degradation_ok = True
        if len(full_pass) >= 2:
            base = abs(full_pass[0]["holdout"]["thesis_return_avg_pct"])
            if base > 0:
                floor = base * MAX_DEGRADATION_FRACTION
                later_min = min(
                    r["holdout"]["thesis_return_avg_pct"]
                    for r in full_pass[1:]
                )
                if later_min < floor:
                    degradation_ok = False
                    reasons.append(
                        "HOLDOUT_EDGE_DEGRADES_MORE_THAN_50_PERCENT"
                    )

        status = (
            "WALK_FORWARD_SUPPORTED"
            if not reasons
            else "WALK_FORWARD_NOT_SUPPORTED"
        )

        supported.append(
            {
                "factor_family": key[0],
                "factor": key[1],
                "state": key[2],
                "direction": key[3],
                "horizon": key[4],
                "selected_holdouts": selected_holdouts,
                "passed_holdouts": passed_holdouts,
                "full_year_holdouts": full_year,
                "full_year_passed": full_year_passed,
                "minimum_passed_holdout_n": min_n,
                "minimum_passed_holdout_thesis_return_pct": worst_return,
                "minimum_passed_holdout_hit_rate_pct": worst_hit,
                "degradation_gate_pass": degradation_ok,
                "status": status,
                "reasons": reasons,
                "folds": recs,
            }
        )

    supported.sort(
        key=lambda x: (
            x["status"] != "WALK_FORWARD_SUPPORTED",
            -x["passed_holdouts"],
            -(x["minimum_passed_holdout_thesis_return_pct"] or -9999),
            x["factor_family"],
            x["factor"],
            x["state"],
        )
    )

    winners = [
        x for x in supported if x["status"] == "WALK_FORWARD_SUPPORTED"
    ]

    result = {
        "version": VERSION,
        "governance": {
            "research_only": True,
            "database_writes": False,
            "production_authority_effect": False,
            "production_model_mutation": False,
            "production_threshold_change": False,
            "production_weight_change": False,
            "automatic_shadow_activation": False,
            "automatic_champion_promotion": False,
            "bearish_inversion_forbidden": True,
        },
        "lineage": {
            "input": str(inp),
            "input_version": audit["version"],
            "input_coverage": audit.get("coverage"),
        },
        "methodology": {
            "expanding_window": True,
            "training_only_selection": True,
            "full_sample_1_1_research_screen_used_for_holdout_selection": False,
            "holdout_years": [f["holdout_year"] for f in FOLDS],
            "partial_year_2026_is_supporting_only": True,
            "weekday_excluded": True,
            "exact_alias_states_excluded": True,
            "nonoverlap_source": (
                "1.1 yearly evidence already uses deterministic "
                "non-overlapping cohorts"
            ),
            "matched_excess_holdout_limitation": (
                "1.1 does not persist year-specific matched-control residuals; "
                "therefore full-sample matched excess is lineage/reference only "
                "and cannot rescue or determine a holdout pass"
            ),
            "next_hardening_if_supported": (
                "materialize fold-native year-specific matched controls before "
                "shadow certification"
            ),
        },
        "summary": {
            "folds": len(fold_reports),
            "candidate_histories": len(supported),
            "walk_forward_supported": len(winners),
            "supported_20d": sum(
                1 for x in winners if x["horizon"] == 20
            ),
            "supported_60d": sum(
                1 for x in winners if x["horizon"] == 60
            ),
            "production_champion_change": False,
        },
        "folds": fold_reports,
        "cohorts": supported,
    }

    policy = {
        "version": VERSION,
        "status": "RESEARCH_POLICY_ONLY",
        "eligible_for_next_research_gate": [
            {
                "factor_family": x["factor_family"],
                "factor": x["factor"],
                "state": x["state"],
                "direction": x["direction"],
                "horizon": x["horizon"],
            }
            for x in winners
        ],
        "authority_effect": False,
        "shadow_activation": False,
        "production_activation": False,
        "next_required_gate": (
            "FOLD_NATIVE_MATCHED_CONTROL_HARDENING_AND_SHADOW_CERTIFICATION"
        ),
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    policy_out.write_text(json.dumps(policy, indent=2) + "\n")

    print(
        json.dumps(
            {
                "status": "READY",
                "version": VERSION,
                "output": str(out),
                "policy_output": str(policy_out),
                "folds": result["summary"]["folds"],
                "candidate_histories": result["summary"][
                    "candidate_histories"
                ],
                "walk_forward_supported": result["summary"][
                    "walk_forward_supported"
                ],
                "supported_20d": result["summary"]["supported_20d"],
                "supported_60d": result["summary"]["supported_60d"],
                "production_champion_change": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
