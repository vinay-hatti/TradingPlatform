#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median, stdev

from sqlalchemy import inspect, text

from trading_ai.database.session import SessionLocal


VERSION = "CYCLICAL-SEASONALITY-RESEARCH-AUDIT-1.1"
DIRECTIONAL = {"BULLISH", "STRONG_BULLISH", "BEARISH", "STRONG_BEARISH"}
BEARISH_DIRECTIONS = {"BEARISH", "STRONG_BEARISH"}
HORIZONS = (20, 60)
MIN_STATE_N = 100
MIN_YEAR_N = 30

# Research-screening gates only. These are not production thresholds.
MIN_MATCHED_EXCESS_BY_HORIZON = {20: 0.25, 60: 0.50}
FDR_Q_MAX = 0.10

FACTOR_FAMILY = {
    "month": "CALENDAR_SEASONALITY",
    "quarter": "CALENDAR_SEASONALITY",
    "month_half": "CALENDAR_SEASONALITY",
    "week_of_month": "CALENDAR_POSITION",
    "weekday": "WEEKDAY_DIAGNOSTIC",
    "opex_phase_proxy": "OPEX_PROXY",
    "volatility_state": "VOLATILITY_CONTEXT",
    "volatility_percentile_band": "VOLATILITY_CONTEXT",
    "regime_age_bucket": "STATE_PERSISTENCE",
    "trend_age_bucket": "STATE_PERSISTENCE",
    "breadth_age_bucket": "STATE_PERSISTENCE",
    "category_age_bucket": "STATE_PERSISTENCE",
    "structure_age_bucket": "STATE_PERSISTENCE",
}


def sha256(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def score_band(v):
    try:
        x = float(v)
    except Exception:
        return "UNKNOWN"
    lo = max(0, min(90, int(math.floor(x / 10) * 10)))
    return f"[{lo},{lo + 10})"


def third_friday(y, m):
    fs = [
        d
        for d in calendar.Calendar().itermonthdates(y, m)
        if d.month == m and d.weekday() == 4
    ]
    return fs[2]


def opex_phase(d, tdates, tidx):
    exp = third_friday(d.year, d.month)
    elig = [x for x in tdates if x.year == d.year and x.month == d.month and x <= exp]
    if not elig or d not in tidx:
        return "UNKNOWN"
    e = max(elig)
    delta = tidx[d] - tidx[e]
    if delta == 0:
        return "OPEX_SESSION"
    if -5 <= delta <= -1:
        return "PRE_OPEX_1_5"
    if -10 <= delta <= -6:
        return "PRE_OPEX_6_10"
    if 1 <= delta <= 5:
        return "POST_OPEX_1_5"
    if 6 <= delta <= 10:
        return "POST_OPEX_6_10"
    return "OUTSIDE_10"


def pband(v):
    try:
        x = float(v)
    except Exception:
        return "UNKNOWN"
    if x < 20:
        return "P00_20"
    if x < 40:
        return "P20_40"
    if x < 60:
        return "P40_60"
    if x < 80:
        return "P60_80"
    return "P80_100"


def age_bucket(n):
    if n <= 1:
        return "AGE_1"
    if n <= 3:
        return "AGE_2_3"
    if n <= 6:
        return "AGE_4_6"
    if n <= 12:
        return "AGE_7_12"
    return "AGE_13_PLUS"


def align_return(direction, raw_return):
    """
    Convert an underlying return into thesis-aligned return.

    Positive always means the stated directional thesis was correct:
      bullish  -> raw underlying return
      bearish  -> negative raw underlying return
    """
    if raw_return is None:
        return None
    x = float(raw_return)
    return -x if direction in BEARISH_DIRECTIONS else x


def stats(vals):
    if not vals:
        return {"n": 0, "avg": None, "median": None, "hit_rate_pct": None}
    return {
        "n": len(vals),
        "avg": mean(vals),
        "median": median(vals),
        "hit_rate_pct": 100 * sum(v > 0 for v in vals) / len(vals),
    }


def approx_one_sided_positive_pvalue(vals):
    """
    Research diagnostic: normal approximation for H0 mean <= 0 versus mean > 0.
    No production/statistical-certification claim is made from this approximation.
    """
    xs = [float(x) for x in vals if x is not None]
    if len(xs) < 2:
        return None
    sd = stdev(xs)
    if sd == 0:
        return 0.0 if mean(xs) > 0 else 1.0
    z = mean(xs) / (sd / math.sqrt(len(xs)))
    # Normal upper-tail probability.
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def bh_qvalues(pairs):
    """
    Benjamini-Hochberg FDR q-values.
    pairs: iterable[(stable_id, pvalue)] with pvalue not None.
    """
    xs = sorted([(sid, float(p)) for sid, p in pairs], key=lambda z: (z[1], z[0]))
    m = len(xs)
    if not m:
        return {}
    raw = [min(1.0, p * m / rank) for rank, (_, p) in enumerate(xs, start=1)]
    adj = list(raw)
    for i in range(m - 2, -1, -1):
        adj[i] = min(adj[i], adj[i + 1])
    return {xs[i][0]: adj[i] for i in range(m)}


def discover_tables(s):
    tabs = set(inspect(s.get_bind()).get_table_names())
    p = [t for t in tabs if t.startswith("historical_underlying_replay") and "prediction" in t]
    o = [t for t in tabs if t.startswith("historical_underlying_replay") and "outcome" in t]
    if not p or not o:
        raise RuntimeError(f"M77 replay tables not found: predictions={p} outcomes={o}")
    return sorted(p)[0], sorted(o)[0]


def cols(s, t):
    return {c["name"] for c in inspect(s.get_bind()).get_columns(t)}


def load_rows(s, pred, out):
    pc, oc = cols(s, pred), cols(s, out)
    reqp = {"replay_run_id", "symbol", "as_of", "direction", "overall_score"}
    reqo = {"replay_run_id", "symbol", "as_of", "return_20d_pct", "return_60d_pct"}
    if reqp - pc or reqo - oc:
        raise RuntimeError(
            f"M77 schema mismatch pred={sorted(reqp-pc)} out={sorted(reqo-oc)}"
        )
    cat = "p.primary_category" if "primary_category" in pc else "NULL"
    prof = "p.profile_json" if "profile_json" in pc else "NULL"
    q = f"""SELECT p.replay_run_id,p.symbol,p.as_of,p.direction,p.overall_score,
    {cat} AS primary_category,{prof} AS profile_json,
    o.return_20d_pct,o.return_60d_pct
    FROM {pred} p JOIN {out} o
      ON o.replay_run_id=p.replay_run_id AND o.symbol=p.symbol AND o.as_of=p.as_of
    WHERE p.direction IN ('BULLISH','STRONG_BULLISH','BEARISH','STRONG_BEARISH')
      AND (o.return_20d_pct IS NOT NULL OR o.return_60d_pct IS NOT NULL)
    ORDER BY p.as_of,p.symbol"""
    return [dict(r) for r in s.execute(text(q)).mappings().all()]


def load_spy_dates(s):
    insp = inspect(s.get_bind())
    cs = {c["name"] for c in insp.get_columns("price_history")}
    dc = "date" if "date" in cs else ("timestamp" if "timestamp" in cs else None)
    if not dc:
        raise RuntimeError("price_history has no recognized date/timestamp column")
    xs = s.execute(
        text(f"SELECT DISTINCT {dc} FROM price_history WHERE symbol='SPY' ORDER BY {dc}")
    ).scalars().all()
    out = []
    for x in xs:
        if isinstance(x, datetime):
            x = x.date()
        elif isinstance(x, str):
            x = date.fromisoformat(x[:10])
        out.append(x)
    return out


def structure(profile):
    if not isinstance(profile, dict):
        return "UNKNOWN"
    for path in (
        ("structure",),
        ("structural_state",),
        ("trend_structure",),
        ("intelligence", "structure"),
        ("setup", "structure"),
    ):
        x = profile
        for k in path:
            if not isinstance(x, dict) or k not in x:
                break
            x = x[k]
        else:
            if x is not None:
                return str(x)
    return "UNKNOWN"


def add_age(rows, src, dst):
    by = defaultdict(list)
    for r in rows:
        by[r["symbol"]].append(r)
    for rs in by.values():
        rs.sort(key=lambda r: r["as_of"])
        last = None
        age = 0
        for r in rs:
            v = r[src]
            age = age + 1 if v == last else 1
            last = v
            r[dst] = age_bucket(age)


def nonoverlap(rows, h, tidx):
    out = []
    by = defaultdict(list)
    for r in rows:
        if r["as_of"] in tidx:
            by[r["symbol"]].append(r)
    for rs in by.values():
        rs.sort(key=lambda r: r["as_of"])
        last = -10**9
        for r in rs:
            i = tidx[r["as_of"]]
            if i - last >= h:
                out.append(r)
                last = i
    return out


def observation_key(r):
    return (str(r["replay_run_id"]), str(r["symbol"]), str(r["as_of"]))


def detect_factor_aliases(data, factors):
    memberships = {}
    for factor in factors:
        states = sorted(
            {
                str(r.get(factor))
                for r in data
                if str(r.get(factor, "UNKNOWN")) != "UNKNOWN"
            }
        )
        for state in states:
            memberships[(factor, state)] = {
                observation_key(r) for r in data if str(r.get(factor)) == state
            }

    exact = []
    keys = sorted(memberships)
    aliased = set()
    for i, a in enumerate(keys):
        sa = memberships[a]
        if not sa:
            continue
        for b in keys[i + 1 :]:
            if a[0] == b[0]:
                continue
            sb = memberships[b]
            if sa == sb and sb:
                exact.append(
                    {
                        "left_factor": a[0],
                        "left_state": a[1],
                        "right_factor": b[0],
                        "right_state": b[1],
                        "observations": len(sa),
                        "membership_jaccard": 1.0,
                    }
                )
                aliased.add(a)
                aliased.add(b)
    return exact, aliased


def matched(allrows, cohort, factor, state, h):
    rk = f"return_{h}d_pct"
    pools = defaultdict(list)
    for r in allrows:
        if r.get(factor) == state or r.get(rk) is None:
            continue
        aligned = align_return(r["direction"], r[rk])
        pools[(r["direction"], r["historical_regime"], r["score_band"])].append(aligned)

    controls = []
    residuals = []
    candidate_aligned = []
    for r in cohort:
        if r.get(rk) is None:
            continue
        cand = align_return(r["direction"], r[rk])
        candidate_aligned.append(cand)
        v = pools.get((r["direction"], r["historical_regime"], r["score_band"]))
        if v:
            ctl = mean(v)
            controls.append(ctl)
            residuals.append(cand - ctl)

    avg = mean(controls) if controls else None
    cr = mean(candidate_aligned) if candidate_aligned else None
    excess = None if avg is None or cr is None else cr - avg
    return {
        "matched_observations": len(controls),
        "matched_control_thesis_return_avg_pct": avg,
        "matched_excess_thesis_return_avg_pct": excess,
        "matched_excess_pvalue_approx": approx_one_sided_positive_pvalue(residuals),
        "control_contract": (
            "same direction + M77.3 PIT regime + score band; tested temporal state "
            "excluded; raw underlying returns directionally aligned before comparison"
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--m77-3",
        default="reports/m77/m77_3_conditional_edge_attribution.json",
    )
    ap.add_argument(
        "--manifest",
        default="reports/m77/certified/m77_2_multiyear_frozen_champion_manifest.json",
    )
    ap.add_argument(
        "--output",
        default="reports/cyclical_seasonality/cyclical_seasonality_research_audit.json",
    )
    a = ap.parse_args()
    m3, man, out = Path(a.m77_3), Path(a.manifest), Path(a.output)
    if not m3.exists() or not man.exists():
        raise SystemExit("Certified M77.2 manifest and M77.3 attribution are required")

    j3 = json.loads(m3.read_text())
    snaps = {
        date.fromisoformat(str(x["as_of"])[:10]): x
        for x in j3["historical_regime_authority"]["snapshots"]
    }

    with SessionLocal() as s:
        pred, oc = discover_tables(s)
        rows = load_rows(s, pred, oc)
        td = load_spy_dates(s)

    tidx = {d: i for i, d in enumerate(td)}
    data = []
    for r in rows:
        d = r["as_of"]
        d = (
            d.date()
            if isinstance(d, datetime)
            else (date.fromisoformat(d[:10]) if isinstance(d, str) else d)
        )
        if d not in snaps:
            continue
        x = dict(r)
        x["as_of"] = d
        sp = snaps[d]
        x["score_band"] = score_band(x["overall_score"])
        x["primary_category"] = str(x.get("primary_category") or "UNKNOWN")
        x["structure"] = structure(x.get("profile_json"))
        x["historical_regime"] = str(sp.get("regime", "UNKNOWN"))
        x["month"] = f"M{d.month:02d}"
        x["quarter"] = f"Q{((d.month - 1) // 3) + 1}"
        x["week_of_month"] = f"W{((d.day - 1) // 7) + 1}"
        x["month_half"] = "H1" if d.day <= 15 else "H2"
        x["weekday"] = calendar.day_name[d.weekday()].upper()
        x["opex_phase_proxy"] = opex_phase(d, td, tidx)
        x["volatility_state"] = str(sp.get("volatility_state", "UNKNOWN"))
        x["volatility_percentile_band"] = pband(sp.get("vol20_percentile_252"))
        x["trend_state"] = str(sp.get("trend_state", "UNKNOWN"))
        x["breadth_state"] = str(sp.get("breadth_state", "UNKNOWN"))
        data.append(x)

    for src, dst in (
        ("historical_regime", "regime_age_bucket"),
        ("trend_state", "trend_age_bucket"),
        ("breadth_state", "breadth_age_bucket"),
        ("primary_category", "category_age_bucket"),
        ("structure", "structure_age_bucket"),
    ):
        add_age(data, src, dst)

    factors = [
        "month",
        "quarter",
        "week_of_month",
        "month_half",
        "weekday",
        "opex_phase_proxy",
        "volatility_state",
        "volatility_percentile_band",
        "regime_age_bucket",
        "trend_age_bucket",
        "breadth_age_bucket",
        "category_age_bucket",
        "structure_age_bucket",
    ]

    exact_alias_pairs, aliased_factor_states = detect_factor_aliases(data, factors)

    coverage = {}
    evidence = []
    for factor in factors:
        counts = defaultdict(int)
        for r in data:
            counts[str(r.get(factor, "UNKNOWN"))] += 1
        coverage[factor] = dict(sorted(counts.items(), key=lambda z: (-z[1], z[0])))

        for state in sorted(counts):
            if state == "UNKNOWN":
                continue
            factor_state_aliased = (factor, state) in aliased_factor_states
            for direction in sorted(DIRECTIONAL):
                cohort = [
                    r
                    for r in data
                    if str(r.get(factor)) == state and r["direction"] == direction
                ]
                if len(cohort) < MIN_STATE_N:
                    continue
                for h in HORIZONS:
                    rk = f"return_{h}d_pct"
                    real = [r for r in cohort if r.get(rk) is not None]
                    if len(real) < MIN_STATE_N:
                        continue
                    no = nonoverlap(real, h, tidx)

                    raw_vals = [float(r[rk]) for r in real]
                    thesis_vals = [align_return(r["direction"], r[rk]) for r in real]
                    raw_no_vals = [float(r[rk]) for r in no]
                    thesis_no_vals = [align_return(r["direction"], r[rk]) for r in no]

                    raw_s = stats(raw_vals)
                    thesis_s = stats(thesis_vals)
                    raw_ns = stats(raw_no_vals)
                    thesis_ns = stats(thesis_no_vals)

                    yearly = []
                    for y in sorted({r["as_of"].year for r in no}):
                        yrs = [r for r in no if r["as_of"].year == y]
                        if len(yrs) >= MIN_YEAR_N:
                            raw_y = stats([float(r[rk]) for r in yrs])
                            th_y = stats(
                                [align_return(r["direction"], r[rk]) for r in yrs]
                            )
                            yearly.append(
                                {
                                    "year": y,
                                    "observations": th_y["n"],
                                    "raw_underlying_return_avg_pct": raw_y["avg"],
                                    "thesis_return_avg_pct": th_y["avg"],
                                    "directional_hit_rate_pct": th_y["hit_rate_pct"],
                                }
                            )

                    ctl = matched(data, real, factor, state, h)
                    stable_id = f"{factor}::{state}::{direction}::{h}"
                    evidence.append(
                        {
                            "_stable_id": stable_id,
                            "factor_family": FACTOR_FAMILY[factor],
                            "factor": factor,
                            "state": state,
                            "direction": direction,
                            "horizon": h,
                            "raw_observations": raw_s["n"],
                            "raw_underlying_return_avg_pct": raw_s["avg"],
                            "raw_underlying_positive_rate_pct": raw_s["hit_rate_pct"],
                            "raw_thesis_return_avg_pct": thesis_s["avg"],
                            "raw_directional_hit_rate_pct": thesis_s["hit_rate_pct"],
                            "non_overlapping_observations": thesis_ns["n"],
                            "non_overlapping_raw_underlying_return_avg_pct": raw_ns["avg"],
                            "non_overlapping_thesis_return_avg_pct": thesis_ns["avg"],
                            "non_overlapping_directional_hit_rate_pct": thesis_ns[
                                "hit_rate_pct"
                            ],
                            "qualified_years": len(yearly),
                            "positive_years": sum(
                                y["thesis_return_avg_pct"] > 0 for y in yearly
                            ),
                            "yearly": yearly,
                            "matched_control": ctl,
                            "promotion_eligibility": {
                                "weekday_eligible": factor != "weekday",
                                "independent_factor_state": not factor_state_aliased,
                                "eligible_for_walk_forward_screen": (
                                    factor != "weekday" and not factor_state_aliased
                                ),
                            },
                            "production_effect": False,
                        }
                    )

    qmap = bh_qvalues(
        (e["_stable_id"], e["matched_control"]["matched_excess_pvalue_approx"])
        for e in evidence
        if e["matched_control"]["matched_excess_pvalue_approx"] is not None
    )

    for e in evidence:
        q = qmap.get(e["_stable_id"])
        e["matched_control"]["matched_excess_fdr_qvalue"] = q
        yearly = e["yearly"]
        excess = e["matched_control"]["matched_excess_thesis_return_avg_pct"]
        flags = {
            "sample_ge_100": e["non_overlapping_observations"] >= MIN_STATE_N,
            "years_ge_3": len(yearly) >= 3,
            "positive_year_rate_ge_75": (
                len(yearly) > 0
                and 100
                * sum(y["thesis_return_avg_pct"] > 0 for y in yearly)
                / len(yearly)
                >= 75
            ),
            "positive_nonoverlap_thesis_return": (
                e["non_overlapping_thesis_return_avg_pct"] is not None
                and e["non_overlapping_thesis_return_avg_pct"] > 0
            ),
            "matched_excess_effect_floor": (
                excess is not None
                and excess >= MIN_MATCHED_EXCESS_BY_HORIZON[e["horizon"]]
            ),
            "fdr_q_le_0_10": q is not None and q <= FDR_Q_MAX,
            "walk_forward_factor_eligible": e["promotion_eligibility"][
                "eligible_for_walk_forward_screen"
            ],
        }
        e["screening_flags"] = flags
        e["research_screen"] = (
            "HYPOTHESIS_WORTH_WALK_FORWARD"
            if all(flags.values())
            else "DESCRIPTIVE_ONLY"
        )
        del e["_stable_id"]

    evidence.sort(
        key=lambda e: (
            e["research_screen"] != "HYPOTHESIS_WORTH_WALK_FORWARD",
            e["factor_family"],
            -(e["matched_control"]["matched_excess_thesis_return_avg_pct"] or -9999),
            -e["non_overlapping_observations"],
        )
    )

    qualified_by_family = defaultdict(list)
    for e in evidence:
        if e["research_screen"] == "HYPOTHESIS_WORTH_WALK_FORWARD":
            qualified_by_family[e["factor_family"]].append(e)

    family_ranking = []
    for family, xs in qualified_by_family.items():
        top = sorted(
            xs,
            key=lambda e: (
                -(e["matched_control"]["matched_excess_thesis_return_avg_pct"] or -9999),
                -e["non_overlapping_observations"],
            ),
        )[0]
        family_ranking.append(
            {
                "factor_family": family,
                "qualified_hypotheses": len(xs),
                "top_factor": top["factor"],
                "top_state": top["state"],
                "top_direction": top["direction"],
                "top_horizon": top["horizon"],
                "top_matched_excess_thesis_return_avg_pct": top["matched_control"][
                    "matched_excess_thesis_return_avg_pct"
                ],
                "top_fdr_qvalue": top["matched_control"]["matched_excess_fdr_qvalue"],
            }
        )
    family_ranking.sort(
        key=lambda x: (
            -(x["top_matched_excess_thesis_return_avg_pct"] or -9999),
            x["factor_family"],
        )
    )

    direction_summary = defaultdict(lambda: {"candidate_rows": 0, "qualified": 0})
    for e in evidence:
        direction_summary[e["direction"]]["candidate_rows"] += 1
        if e["research_screen"] == "HYPOTHESIS_WORTH_WALK_FORWARD":
            direction_summary[e["direction"]]["qualified"] += 1

    result = {
        "version": VERSION,
        "governance": {
            "mode": "READ_ONLY_CYCLICAL_SEASONALITY_ATTRIBUTION",
            "research_only": True,
            "read_only_database": True,
            "database_writes": False,
            "production_authority_effect": False,
            "production_model_mutation": False,
            "production_threshold_change": False,
            "production_weight_change": False,
            "automatic_champion_promotion": False,
        },
        "lineage": {
            "m77_2_manifest": str(man),
            "m77_2_manifest_sha256": sha256(man),
            "m77_3_attribution": str(m3),
            "m77_3_attribution_sha256": sha256(m3),
            "replay_prediction_table": pred,
            "replay_outcome_table": oc,
        },
        "coverage": {
            "observations": len(data),
            "symbols": len({r["symbol"] for r in data}),
            "first_as_of": str(min(r["as_of"] for r in data)) if data else None,
            "last_as_of": str(max(r["as_of"] for r in data)) if data else None,
            "replay_dates": len({r["as_of"] for r in data}),
        },
        "methodology": {
            "horizons": [20, 60],
            "screening_only": True,
            "walk_forward_required_before_any_shadow_or_production_use": True,
            "directional_return_contract": {
                "bullish": "thesis_return = raw_underlying_return",
                "bearish": "thesis_return = -raw_underlying_return",
                "positive_thesis_return_meaning": "directional thesis correct",
            },
            "effect_size_floor_pct": MIN_MATCHED_EXCESS_BY_HORIZON,
            "multiple_testing": {
                "method": "BENJAMINI_HOCHBERG",
                "family_scope": "all tested factor/state/direction/horizon rows with matched residual p-value",
                "pvalue_method": "one-sided positive matched-residual mean, normal approximation",
                "qvalue_gate": FDR_Q_MAX,
                "diagnostic_not_production_certification": True,
            },
        },
        "factor_coverage": coverage,
        "factor_limitations": {
            "weekday": (
                "M77 replay cadence is weekly; weekday is diagnostic-only and cannot "
                "qualify for walk-forward promotion"
            ),
            "opex_phase_proxy": (
                "Monthly third-Friday proxy mapped to observed SPY sessions; not exact "
                "historical expiration authority"
            ),
            "aliasing": (
                "Exact cross-factor membership aliases are detected and both aliased "
                "factor-states are excluded from walk-forward qualification"
            ),
            "age_factors": "Measured in consecutive replay observations, not daily trading sessions",
            "survivorship_bias_free_claim": False,
            "pit_sector_membership_claim": False,
        },
        "alias_diagnostics": {
            "exact_alias_pairs": exact_alias_pairs,
            "aliased_factor_states": [
                {"factor": f, "state": s}
                for f, s in sorted(aliased_factor_states)
            ],
        },
        "screening_summary": {
            "candidate_rows": len(evidence),
            "hypotheses_worth_walk_forward": sum(
                e["research_screen"] == "HYPOTHESIS_WORTH_WALK_FORWARD"
                for e in evidence
            ),
            "by_direction": dict(sorted(direction_summary.items())),
        },
        "independent_factor_family_ranking": family_ranking,
        "evidence": evidence,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str) + "\n")

    print(
        json.dumps(
            {
                "status": "READY",
                "version": VERSION,
                "output": str(out),
                "coverage": result["coverage"],
                "screening_summary": result["screening_summary"],
                "exact_alias_pairs": len(exact_alias_pairs),
                "independent_factor_families": len(family_ranking),
                "production_authority_effect": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
