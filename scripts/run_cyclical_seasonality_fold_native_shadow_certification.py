#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, stdev

from trading_ai.database.session import SessionLocal


VERSION = "CYCLICAL-SEASONALITY-FOLD-NATIVE-MATCHED-CONTROL-SHADOW-CERT-1.0"
AUDIT_VERSION = "CYCLICAL-SEASONALITY-RESEARCH-AUDIT-1.1"
WALK_FORWARD_VERSION = "CYCLICAL-SEASONALITY-WALK-FORWARD-CERTIFICATION-1.0"

DEFAULT_AUDIT = Path(
    "reports/cyclical_seasonality/cyclical_seasonality_research_audit.json"
)
DEFAULT_WALK_FORWARD = Path(
    "reports/cyclical_seasonality/cyclical_seasonality_walk_forward_certification.json"
)
DEFAULT_M77_3 = Path("reports/m77/m77_3_conditional_edge_attribution.json")
DEFAULT_OUTPUT = Path(
    "reports/cyclical_seasonality/"
    "cyclical_seasonality_fold_native_shadow_certification.json"
)
DEFAULT_POLICY = Path(
    "reports/cyclical_seasonality/"
    "cyclical_seasonality_fold_native_shadow_policy.json"
)
AUDIT_SCRIPT = Path("scripts/run_cyclical_seasonality_research_audit.py")

FULL_YEAR_HOLDOUTS = (2024, 2025)
PARTIAL_YEAR_HOLDOUT = 2026
MIN_MATCHED_OBSERVATIONS = 100
MIN_MATCHED_COVERAGE_PCT = 80.0
MIN_MATCHED_EXCESS_BY_HORIZON = {20: 0.25, 60: 0.50}
FDR_Q_MAX = 0.10
REDUNDANCY_JACCARD = 0.90


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text())


def load_audit_module(path: Path):
    if not path.exists():
        raise SystemExit(f"Required installed Audit 1.1 source missing: {path}")
    spec = importlib.util.spec_from_file_location("cyclical_seasonality_audit_1_1", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load Audit 1.1 source: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if getattr(mod, "VERSION", None) != AUDIT_VERSION:
        raise SystemExit(
            f"Installed audit source is not {AUDIT_VERSION}: "
            f"{getattr(mod, 'VERSION', None)}"
        )
    return mod


def approx_one_sided_positive_pvalue(vals):
    xs = [float(x) for x in vals if x is not None]
    if len(xs) < 2:
        return None
    sd = stdev(xs)
    if sd == 0:
        return 0.0 if mean(xs) > 0 else 1.0
    z = mean(xs) / (sd / math.sqrt(len(xs)))
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def bh_qvalues(pairs):
    xs = sorted([(sid, float(p)) for sid, p in pairs], key=lambda z: (z[1], z[0]))
    m = len(xs)
    if not m:
        return {}
    vals = [min(1.0, p * m / rank) for rank, (_, p) in enumerate(xs, start=1)]
    for i in range(m - 2, -1, -1):
        vals[i] = min(vals[i], vals[i + 1])
    return {xs[i][0]: vals[i] for i in range(m)}


def normalize_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def build_observation_data(audit_mod, m77_3: dict):
    snapshots = {
        normalize_date(x["as_of"]): x
        for x in m77_3["historical_regime_authority"]["snapshots"]
    }

    with SessionLocal() as session:
        pred, out = audit_mod.discover_tables(session)
        rows = audit_mod.load_rows(session, pred, out)
        trading_dates = audit_mod.load_spy_dates(session)

    tidx = {d: i for i, d in enumerate(trading_dates)}
    data = []
    for r in rows:
        d = normalize_date(r["as_of"])
        snap = snapshots.get(d)
        if snap is None:
            continue
        x = dict(r)
        x["as_of"] = d
        x["score_band"] = audit_mod.score_band(x["overall_score"])
        x["primary_category"] = str(x.get("primary_category") or "UNKNOWN")
        x["structure"] = audit_mod.structure(x.get("profile_json"))
        x["historical_regime"] = str(snap.get("regime", "UNKNOWN"))
        x["month"] = f"M{d.month:02d}"
        x["quarter"] = f"Q{((d.month - 1) // 3) + 1}"
        x["week_of_month"] = f"W{((d.day - 1) // 7) + 1}"
        x["month_half"] = "H1" if d.day <= 15 else "H2"
        x["weekday"] = __import__("calendar").day_name[d.weekday()].upper()
        x["opex_phase_proxy"] = audit_mod.opex_phase(d, trading_dates, tidx)
        x["volatility_state"] = str(snap.get("volatility_state", "UNKNOWN"))
        x["volatility_percentile_band"] = audit_mod.pband(
            snap.get("vol20_percentile_252")
        )
        x["trend_state"] = str(snap.get("trend_state", "UNKNOWN"))
        x["breadth_state"] = str(snap.get("breadth_state", "UNKNOWN"))
        data.append(x)

    for src, dst in (
        ("historical_regime", "regime_age_bucket"),
        ("trend_state", "trend_age_bucket"),
        ("breadth_state", "breadth_age_bucket"),
        ("primary_category", "category_age_bucket"),
        ("structure", "structure_age_bucket"),
    ):
        audit_mod.add_age(data, src, dst)

    return data, tidx, pred, out


def key(c):
    return (
        c["factor_family"],
        c["factor"],
        c["state"],
        c["direction"],
        int(c["horizon"]),
    )


def cohort_id(c):
    return "::".join(map(str, key(c)))


def supported_candidates(walk_forward: dict):
    return [
        c
        for c in walk_forward.get("cohorts", [])
        if c.get("status") == "WALK_FORWARD_SUPPORTED"
    ]


def fold_native_matched_control(
    audit_mod,
    data,
    tidx,
    candidate,
    holdout_year,
):
    """
    Strict fold-native control:
      - holdout-year only;
      - candidate direction only;
      - same replay/as-of date;
      - same M77.3 PIT historical regime;
      - same overall-score band;
      - tested temporal factor state excluded;
      - candidate symbol excluded from its own control;
      - raw underlying control returns aligned to candidate direction.

    No future holdout information is used to construct another holdout's control.
    """
    factor = candidate["factor"]
    state = str(candidate["state"])
    direction = candidate["direction"]
    horizon = int(candidate["horizon"])
    rk = f"return_{horizon}d_pct"

    cohort_all = [
        r
        for r in data
        if r["as_of"].year == holdout_year
        and r["direction"] == direction
        and str(r.get(factor, "UNKNOWN")) == state
        and r.get(rk) is not None
    ]
    cohort = audit_mod.nonoverlap(cohort_all, horizon, tidx)

    controls_by_match = defaultdict(list)
    for r in data:
        if r["as_of"].year != holdout_year or r.get(rk) is None:
            continue
        if r["direction"] != direction:
            continue
        if str(r.get(factor, "UNKNOWN")) == state:
            continue
        mk = (r["as_of"], r["historical_regime"], r["score_band"])
        controls_by_match[mk].append(r)

    residuals = []
    control_means = []
    thesis_returns = []
    matched_candidate_rows = []

    for r in cohort:
        mk = (r["as_of"], r["historical_regime"], r["score_band"])
        pool = [
            x for x in controls_by_match.get(mk, [])
            if x["symbol"] != r["symbol"]
        ]
        if not pool:
            continue

        cand = audit_mod.align_return(direction, r[rk])
        ctl = mean(audit_mod.align_return(direction, x[rk]) for x in pool)
        residuals.append(cand - ctl)
        control_means.append(ctl)
        thesis_returns.append(cand)
        matched_candidate_rows.append(r)

    matched_n = len(residuals)
    candidate_n = len(cohort)
    coverage_pct = 100.0 * matched_n / candidate_n if candidate_n else 0.0
    excess = mean(residuals) if residuals else None

    return {
        "holdout_year": holdout_year,
        "holdout_credit": (
            "FULL_YEAR" if holdout_year in FULL_YEAR_HOLDOUTS else "PARTIAL_YEAR"
        ),
        "candidate_non_overlapping_observations": candidate_n,
        "matched_observations": matched_n,
        "matched_coverage_pct": coverage_pct,
        "candidate_thesis_return_avg_pct": (
            mean(thesis_returns) if thesis_returns else None
        ),
        "matched_control_thesis_return_avg_pct": (
            mean(control_means) if control_means else None
        ),
        "matched_excess_thesis_return_avg_pct": excess,
        "matched_excess_pvalue_approx": approx_one_sided_positive_pvalue(residuals),
        "candidate_observation_keys": [
            f'{r["replay_run_id"]}|{r["symbol"]}|{r["as_of"]}'
            for r in matched_candidate_rows
        ],
        "control_contract": (
            "fold-native holdout-year only; same candidate direction + same replay "
            "date + M77.3 PIT regime + overall-score band; tested temporal state "
            "excluded; candidate symbol excluded; control raw underlying returns "
            "aligned to candidate direction"
        ),
    }


def apply_fold_fdr(records):
    for year in FULL_YEAR_HOLDOUTS + (PARTIAL_YEAR_HOLDOUT,):
        for horizon in (20, 60):
            rows = [
                r for r in records
                if r["holdout_year"] == year
                and r["horizon"] == horizon
                and r["matched"]["matched_excess_pvalue_approx"] is not None
            ]
            qmap = bh_qvalues(
                (r["candidate_id"], r["matched"]["matched_excess_pvalue_approx"])
                for r in rows
            )
            for r in rows:
                r["matched"]["matched_excess_fdr_qvalue"] = qmap.get(
                    r["candidate_id"]
                )


def fold_verdict(rec):
    m = rec["matched"]
    h = rec["horizon"]
    reasons = []
    if m["matched_observations"] < MIN_MATCHED_OBSERVATIONS:
        reasons.append("MATCHED_OBSERVATIONS_BELOW_100")
    if m["matched_coverage_pct"] < MIN_MATCHED_COVERAGE_PCT:
        reasons.append("MATCHED_COVERAGE_BELOW_80_PERCENT")
    if (
        m["matched_excess_thesis_return_avg_pct"] is None
        or m["matched_excess_thesis_return_avg_pct"]
        < MIN_MATCHED_EXCESS_BY_HORIZON[h]
    ):
        reasons.append("MATCHED_EXCESS_BELOW_EFFECT_FLOOR")
    if (
        m.get("matched_excess_fdr_qvalue") is None
        or m["matched_excess_fdr_qvalue"] > FDR_Q_MAX
    ):
        reasons.append("MATCHED_EXCESS_FDR_Q_ABOVE_0_10")
    if (
        m["candidate_thesis_return_avg_pct"] is None
        or m["candidate_thesis_return_avg_pct"] <= 0
    ):
        reasons.append("HOLDOUT_THESIS_RETURN_NONPOSITIVE")

    return {
        "passed": not reasons,
        "reasons": reasons,
        "effect_floor_pct": MIN_MATCHED_EXCESS_BY_HORIZON[h],
        "fdr_q_max": FDR_Q_MAX,
    }


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def redundancy_components(certified):
    """
    Collapse highly overlapping certified hypotheses within identical
    direction/horizon. Connected components at Jaccard >= 0.90 are treated as
    one research information family.
    """
    ids = [x["candidate_id"] for x in certified]
    by_id = {x["candidate_id"]: x for x in certified}
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    pairs = []
    for i, a in enumerate(certified):
        for b in certified[i + 1 :]:
            if (
                a["direction"] != b["direction"]
                or a["horizon"] != b["horizon"]
            ):
                continue
            ja = jaccard(
                a["matched_observation_keys"],
                b["matched_observation_keys"],
            )
            if ja >= REDUNDANCY_JACCARD:
                union(a["candidate_id"], b["candidate_id"])
                pairs.append(
                    {
                        "left": a["candidate_id"],
                        "right": b["candidate_id"],
                        "jaccard": ja,
                    }
                )

    groups = defaultdict(list)
    for cid in ids:
        groups[find(cid)].append(cid)

    components = []
    representatives = set()
    redundant = set()
    for members in groups.values():
        ranked = sorted(
            (by_id[c] for c in members),
            key=lambda x: (
                -x["full_year_min_matched_excess_pct"],
                -x["full_year_min_matched_observations"],
                x["factor_family"],
                x["factor"],
                x["state"],
            ),
        )
        rep = ranked[0]["candidate_id"]
        representatives.add(rep)
        redundant.update(x["candidate_id"] for x in ranked[1:])
        components.append(
            {
                "representative": rep,
                "members": [x["candidate_id"] for x in ranked],
                "component_size": len(ranked),
            }
        )

    components.sort(key=lambda x: (-x["component_size"], x["representative"]))
    return components, pairs, representatives, redundant


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default=str(DEFAULT_AUDIT))
    ap.add_argument("--walk-forward", default=str(DEFAULT_WALK_FORWARD))
    ap.add_argument("--m77-3", default=str(DEFAULT_M77_3))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--policy-output", default=str(DEFAULT_POLICY))
    args = ap.parse_args()

    audit_path = Path(args.audit)
    walk_path = Path(args.walk_forward)
    m77_3_path = Path(args.m77_3)
    output = Path(args.output)
    policy_output = Path(args.policy_output)

    for p in (audit_path, walk_path, m77_3_path, AUDIT_SCRIPT):
        if not p.exists():
            raise SystemExit(f"Required input missing: {p}")

    audit = load_json(audit_path)
    walk = load_json(walk_path)
    m77_3 = load_json(m77_3_path)

    if audit.get("version") != AUDIT_VERSION:
        raise SystemExit(f"Expected {AUDIT_VERSION}")
    if walk.get("version") != WALK_FORWARD_VERSION:
        raise SystemExit(f"Expected {WALK_FORWARD_VERSION}")

    # Fail closed if predecessor governance is not research-only.
    if not (
        audit.get("governance", {}).get("production_authority_effect") is False
        and audit.get("governance", {}).get("database_writes") is False
        and walk.get("governance", {}).get("production_authority_effect") is False
        and walk.get("governance", {}).get("database_writes") is False
        and walk.get("governance", {}).get("automatic_shadow_activation") is False
    ):
        raise SystemExit("Predecessor governance is not fail-closed")

    audit_mod = load_audit_module(AUDIT_SCRIPT)
    data, tidx, pred_table, outcome_table = build_observation_data(
        audit_mod, m77_3
    )

    candidates = supported_candidates(walk)
    fold_records = []
    for c in candidates:
        for year in FULL_YEAR_HOLDOUTS + (PARTIAL_YEAR_HOLDOUT,):
            matched = fold_native_matched_control(
                audit_mod, data, tidx, c, year
            )
            fold_records.append(
                {
                    "candidate_id": cohort_id(c),
                    "factor_family": c["factor_family"],
                    "factor": c["factor"],
                    "state": c["state"],
                    "direction": c["direction"],
                    "horizon": int(c["horizon"]),
                    "holdout_year": year,
                    "holdout_credit": matched["holdout_credit"],
                    "matched": matched,
                }
            )

    apply_fold_fdr(fold_records)
    for r in fold_records:
        r["verdict"] = fold_verdict(r)

    by_candidate = defaultdict(list)
    for r in fold_records:
        by_candidate[r["candidate_id"]].append(r)

    certifications = []
    for c in candidates:
        cid = cohort_id(c)
        recs = sorted(by_candidate[cid], key=lambda x: x["holdout_year"])
        full = [r for r in recs if r["holdout_year"] in FULL_YEAR_HOLDOUTS]
        partial = [r for r in recs if r["holdout_year"] == PARTIAL_YEAR_HOLDOUT]

        full_pass = all(r["verdict"]["passed"] for r in full) and len(full) == 2
        partial_pass = bool(partial and partial[0]["verdict"]["passed"])

        reasons = []
        if not full_pass:
            reasons.append("BOTH_2024_AND_2025_FOLD_NATIVE_CONTROLS_MUST_PASS")

        if full_pass and partial_pass:
            tier = "SHADOW_CERTIFIED_TIER_1"
        elif full_pass:
            tier = "SHADOW_CERTIFIED_TIER_2"
        else:
            tier = "NOT_SHADOW_CERTIFIED"

        full_excess = [
            r["matched"]["matched_excess_thesis_return_avg_pct"] for r in full
            if r["matched"]["matched_excess_thesis_return_avg_pct"] is not None
        ]
        full_n = [r["matched"]["matched_observations"] for r in full]

        matched_keys = []
        for r in recs:
            matched_keys.extend(r["matched"]["candidate_observation_keys"])

        certifications.append(
            {
                "candidate_id": cid,
                "factor_family": c["factor_family"],
                "factor": c["factor"],
                "state": c["state"],
                "direction": c["direction"],
                "horizon": int(c["horizon"]),
                "walk_forward_status": c["status"],
                "shadow_certification_tier_pre_redundancy": tier,
                "full_year_fold_native_pass": full_pass,
                "partial_2026_support_pass": partial_pass,
                "full_year_min_matched_excess_pct": min(full_excess)
                if full_excess else None,
                "full_year_min_matched_observations": min(full_n)
                if full_n else 0,
                "folds": recs,
                "reasons": reasons,
                "matched_observation_keys": sorted(set(matched_keys)),
            }
        )

    pre_certified = [
        x for x in certifications
        if x["shadow_certification_tier_pre_redundancy"].startswith(
            "SHADOW_CERTIFIED"
        )
    ]

    components, correlated_pairs, representatives, redundant = (
        redundancy_components(pre_certified)
    )

    for x in certifications:
        pre = x["shadow_certification_tier_pre_redundancy"]
        if x["candidate_id"] in redundant:
            x["shadow_certification_status"] = "CORRELATED_REDUNDANT"
            x["shadow_activation_eligible"] = False
            x["reasons"].append(
                "HIGH_MEMBERSHIP_OVERLAP_WITH_STRONGER_CERTIFIED_REPRESENTATIVE"
            )
        elif x["candidate_id"] in representatives and pre.startswith(
            "SHADOW_CERTIFIED"
        ):
            x["shadow_certification_status"] = pre
            x["shadow_activation_eligible"] = False
        else:
            x["shadow_certification_status"] = "NOT_SHADOW_CERTIFIED"
            x["shadow_activation_eligible"] = False

    certifications.sort(
        key=lambda x: (
            not x["shadow_certification_status"].startswith("SHADOW_CERTIFIED"),
            x["shadow_certification_status"] != "SHADOW_CERTIFIED_TIER_1",
            -(x["full_year_min_matched_excess_pct"] or -9999),
            -x["full_year_min_matched_observations"],
            x["candidate_id"],
        )
    )

    tier1 = [
        x for x in certifications
        if x["shadow_certification_status"] == "SHADOW_CERTIFIED_TIER_1"
    ]
    tier2 = [
        x for x in certifications
        if x["shadow_certification_status"] == "SHADOW_CERTIFIED_TIER_2"
    ]

    result = {
        "version": VERSION,
        "status": "READY",
        "governance": {
            "research_only": True,
            "read_only_database": True,
            "database_writes": False,
            "database_migrations": False,
            "production_authority_effect": False,
            "production_model_mutation": False,
            "production_threshold_change": False,
            "production_weight_change": False,
            "production_decision_change": False,
            "automatic_shadow_activation": False,
            "automatic_champion_promotion": False,
        },
        "lineage": {
            "audit_input": str(audit_path),
            "audit_sha256": sha256(audit_path),
            "walk_forward_input": str(walk_path),
            "walk_forward_sha256": sha256(walk_path),
            "m77_3_input": str(m77_3_path),
            "m77_3_sha256": sha256(m77_3_path),
            "audit_source": str(AUDIT_SCRIPT),
            "audit_source_sha256": sha256(AUDIT_SCRIPT),
            "replay_prediction_table": pred_table,
            "replay_outcome_table": outcome_table,
        },
        "methodology": {
            "source_walk_forward_supported_candidates": len(candidates),
            "full_year_holdouts": list(FULL_YEAR_HOLDOUTS),
            "partial_year_supporting_holdout": PARTIAL_YEAR_HOLDOUT,
            "matched_control_contract": (
                "same holdout year + same candidate direction + same replay date + "
                "M77.3 PIT regime + score band; tested temporal state and candidate "
                "symbol excluded"
            ),
            "effect_floor_pct": MIN_MATCHED_EXCESS_BY_HORIZON,
            "minimum_matched_observations": MIN_MATCHED_OBSERVATIONS,
            "minimum_matched_coverage_pct": MIN_MATCHED_COVERAGE_PCT,
            "fold_native_fdr_method": "BENJAMINI_HOCHBERG",
            "fold_native_fdr_scope": "holdout year x horizon among tested walk-forward-supported candidates",
            "fold_native_fdr_q_max": FDR_Q_MAX,
            "tier_1": "2024 + 2025 full-year fold-native passes and 2026 partial-year supporting pass",
            "tier_2": "2024 + 2025 full-year fold-native passes; 2026 partial-year does not pass",
            "redundancy_collapse": (
                f"same direction/horizon candidate membership Jaccard >= "
                f"{REDUNDANCY_JACCARD:.2f}; strongest full-year matched-excess "
                "representative retained"
            ),
        },
        "summary": {
            "walk_forward_supported_input": len(candidates),
            "fold_native_records": len(fold_records),
            "pre_redundancy_shadow_certified": len(pre_certified),
            "shadow_certified_tier_1": len(tier1),
            "shadow_certified_tier_2": len(tier2),
            "correlated_redundant": len(redundant),
            "not_shadow_certified": sum(
                x["shadow_certification_status"] == "NOT_SHADOW_CERTIFIED"
                for x in certifications
            ),
            "production_champion_change": False,
            "shadow_activation": False,
        },
        "redundancy": {
            "jaccard_threshold": REDUNDANCY_JACCARD,
            "components": components,
            "correlated_pairs": correlated_pairs,
        },
        "certifications": certifications,
    }

    policy = {
        "version": VERSION,
        "status": "RESEARCH_SHADOW_POLICY_CERTIFIED",
        "authority_effect": False,
        "automatic_shadow_activation": False,
        "production_activation": False,
        "application_contract": (
            "Research annotation only. A current observation may be tagged with "
            "a listed cyclical/seasonality shadow cohort only after a separate "
            "live-forward capture implementation. This policy must not change "
            "production score, direction, strategy, thresholds, weights, capital "
            "allocation, execution, or portfolio-management authority."
        ),
        "tier_1": [
            {
                "candidate_id": x["candidate_id"],
                "factor_family": x["factor_family"],
                "factor": x["factor"],
                "state": x["state"],
                "direction": x["direction"],
                "horizon": x["horizon"],
                "full_year_min_matched_excess_pct": x[
                    "full_year_min_matched_excess_pct"
                ],
            }
            for x in tier1
        ],
        "tier_2": [
            {
                "candidate_id": x["candidate_id"],
                "factor_family": x["factor_family"],
                "factor": x["factor"],
                "state": x["state"],
                "direction": x["direction"],
                "horizon": x["horizon"],
                "full_year_min_matched_excess_pct": x[
                    "full_year_min_matched_excess_pct"
                ],
            }
            for x in tier2
        ],
        "next_required_gate": (
            "LIVE_FORWARD_CYCLICAL_SEASONALITY_SHADOW_CAPTURE_WITH_ZERO_PRODUCTION_EFFECT"
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    policy_output.write_text(json.dumps(policy, indent=2, default=str) + "\n")

    print(
        json.dumps(
            {
                "status": "READY",
                "version": VERSION,
                "output": str(output),
                "policy_output": str(policy_output),
                "walk_forward_supported_input": len(candidates),
                "pre_redundancy_shadow_certified": len(pre_certified),
                "shadow_certified_tier_1": len(tier1),
                "shadow_certified_tier_2": len(tier2),
                "correlated_redundant": len(redundant),
                "production_authority_effect": False,
                "automatic_shadow_activation": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
