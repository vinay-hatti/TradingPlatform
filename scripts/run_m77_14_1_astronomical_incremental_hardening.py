#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.astronomical_cycles import (
    FROZEN_HYPOTHESES,
    features,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/m77/m77_14_1_astronomical_incremental_certification.json"
PIT = ROOT / "reports/m77/m77_8_daily_pit_regime_snapshots.json"

HORIZONS = (1, 5, 10, 20, 60)
TARGETS = ("SPX", "NDX", "RUT")
PROXIES = {"SPX": "SPY", "NDX": "QQQ", "RUT": "IWM"}

MIN_N = 30
PERMUTATIONS = 10000
RNG_SEED = 771401
PLACEBO_SHIFTS = (-61, -43, -29, -17, 17, 29, 43, 61)

# This milestone does not change the frozen feature definitions from M77.14.
FROZEN_OUTCOMES = (
    "FORWARD_RETURN",
    "ABSOLUTE_RETURN",
    "REALIZED_VOLATILITY",
    "MAX_ADVERSE_EXCURSION",
    "MAX_FAVORABLE_EXCURSION",
    "TURNING_POINT_3_SESSION",
)

def bh(items):
    ordered = sorted(items, key=lambda x: x[1])
    m = len(ordered)
    out = {}
    prev = 1.0
    for i, (key, p) in reversed(list(enumerate(ordered, 1))):
        prev = min(prev, p * m / i)
        out[key] = prev
    return out

def empirical_two_sided_p(observed, null_values):
    if not null_values:
        return 1.0
    center = mean(null_values)
    obs_dev = abs(observed - center)
    more_extreme = sum(abs(x - center) >= obs_dev for x in null_values)
    return (more_extreme + 1) / (len(null_values) + 1)

def load_regimes():
    if not PIT.exists():
        return {}
    x = json.loads(PIT.read_text())
    rows = x if isinstance(x, list) else x.get("snapshots") or x.get("rows") or []
    return {
        str(r.get("as_of"))[:10]: r.get("regime")
        for r in rows
        if r.get("as_of") and r.get("regime")
    }

def resolve(session, target):
    for sym in (target, PROXIES[target], "I:" + target):
        if session.execute(
            text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),
            {"s": sym},
        ).scalar():
            return sym
    return None

def prices(session, symbol):
    return [
        (r[0], float(r[1]))
        for r in session.execute(
            text(
                "SELECT date,close FROM price_history "
                "WHERE symbol=:s AND close IS NOT NULL ORDER BY date"
            ),
            {"s": symbol},
        )
    ]

def daily_returns(close):
    out = [None]
    for i in range(1, len(close)):
        out.append(close[i] / close[i - 1] - 1)
    return out

def local_turning_point(close, i, radius=3):
    if i < radius or i + radius >= len(close):
        return None
    window = close[i - radius : i + radius + 1]
    x = close[i]
    return x == min(window) or x == max(window)

def outcome_vector(close, dret, i, h):
    if i + h >= len(close):
        return None
    fwd = close[i + h] / close[i] - 1
    path = [close[j] / close[i] - 1 for j in range(i + 1, i + h + 1)]
    rv_slice = [x for x in dret[i + 1 : i + h + 1] if x is not None]
    rv = pstdev(rv_slice) * math.sqrt(252) if len(rv_slice) >= 2 else 0.0
    return {
        "FORWARD_RETURN": fwd,
        "ABSOLUTE_RETURN": abs(fwd),
        "REALIZED_VOLATILITY": rv,
        "MAX_ADVERSE_EXCURSION": min(path) if path else 0.0,
        "MAX_FAVORABLE_EXCURSION": max(path) if path else 0.0,
        "TURNING_POINT_3_SESSION": 1.0 if local_turning_point(close, i) else 0.0,
    }

def summarize(values):
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": mean(values)}

def matched_baseline(indices, eligible_indices, values_by_index, dates, regimes, mode):
    if not indices:
        return []
    out = []
    event_set = set(indices)
    for i in indices:
        reg = regimes.get(str(dates[i])[:10])
        month = dates[i].month
        candidates = []
        for j in eligible_indices:
            if j in event_set:
                continue
            if mode == "REGIME":
                if reg is None or regimes.get(str(dates[j])[:10]) != reg:
                    continue
            elif mode == "CALENDAR":
                if dates[j].month != month:
                    continue
            elif mode == "REGIME_CALENDAR":
                if reg is None or regimes.get(str(dates[j])[:10]) != reg:
                    continue
                if dates[j].month != month:
                    continue
            candidates.append(j)
        if candidates:
            out.append(mean(values_by_index[j] for j in candidates))
    return out

def permutation_distribution(rng, event_n, eligible_values, iterations):
    if event_n <= 0 or event_n > len(eligible_values):
        return []
    out = []
    # Sampling without replacement preserves event count and market-return distribution.
    population = list(range(len(eligible_values)))
    for _ in range(iterations):
        idx = rng.sample(population, event_n)
        out.append(mean(eligible_values[j] for j in idx))
    return out

def frozen_shift_placebo(mask, values_by_index, h):
    out = []
    n = len(mask)
    for shift in PLACEBO_SHIFTS:
        vals = []
        for i in range(0, n - h):
            j = i + shift
            if 0 <= j < n and mask[j] and i in values_by_index:
                vals.append(values_by_index[i])
        if vals:
            out.append(mean(vals))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "run"))
    ap.add_argument("--confirm")
    args = ap.parse_args()

    with SessionLocal() as session:
        resolved = {t: resolve(session, t) for t in TARGETS}

    if args.mode == "preflight":
        print(json.dumps({
            "version": "M77.14.1-INCREMENTAL-BASELINE-PERMUTATION-OUTCOME-HARDENING-1.0",
            "status": "READY",
            "confirmation_required": "RUN_M77_14_1_ASTRONOMICAL_HARDENING",
            "targets": resolved,
            "horizons": HORIZONS,
            "frozen_hypotheses": FROZEN_HYPOTHESES,
            "frozen_outcomes": FROZEN_OUTCOMES,
            "permutations_per_test": PERMUTATIONS,
            "baseline_controls": [
                "UNCONDITIONAL_COMPLEMENT",
                "REGIME_MATCHED",
                "CALENDAR_MONTH_MATCHED",
                "REGIME_AND_CALENDAR_MATCHED",
                "FROZEN_SHIFT_PLACEBO",
            ],
            "governance": {
                "hypothesis_search": False,
                "neighboring_window_search": False,
                "database_writes": False,
                "production_authority_effect": False,
                "automatic_promotion": False,
                "traditional_ephemeris_gate": "FAIL_CLOSED_PENDING_INDEPENDENT_PARITY",
            },
        }, indent=2))
        return

    if args.confirm != "RUN_M77_14_1_ASTRONOMICAL_HARDENING":
        raise SystemExit("confirmation required")

    regime = load_regimes()
    tests = []
    pvalues = []
    rng = random.Random(RNG_SEED)

    with SessionLocal() as session:
        for target, symbol in resolved.items():
            if not symbol:
                continue

            rows = prices(session, symbol)
            dates = [r[0] for r in rows]
            close = [r[1] for r in rows]
            dret = daily_returns(close)
            feats = [features(d) for d in dates]

            for h in HORIZONS:
                outcomes = {}
                for i in range(len(rows) - h):
                    vec = outcome_vector(close, dret, i, h)
                    if vec is not None:
                        outcomes[i] = vec

                eligible = sorted(outcomes)

                for hypothesis, meta in FROZEN_HYPOTHESES.items():
                    mask = [bool(x.get(hypothesis)) for x in feats]
                    event_indices = [i for i in eligible if mask[i]]

                    for outcome_name in FROZEN_OUTCOMES:
                        event_values = [outcomes[i][outcome_name] for i in event_indices]
                        eligible_values = [outcomes[i][outcome_name] for i in eligible]
                        if not event_values:
                            continue

                        event_mean = mean(event_values)
                        complement_values = [
                            outcomes[i][outcome_name]
                            for i in eligible
                            if i not in set(event_indices)
                        ]
                        complement_mean = mean(complement_values) if complement_values else None

                        regime_base = matched_baseline(
                            event_indices, eligible, {i: outcomes[i][outcome_name] for i in eligible},
                            dates, regime, "REGIME"
                        )
                        cal_base = matched_baseline(
                            event_indices, eligible, {i: outcomes[i][outcome_name] for i in eligible},
                            dates, regime, "CALENDAR"
                        )
                        regime_cal_base = matched_baseline(
                            event_indices, eligible, {i: outcomes[i][outcome_name] for i in eligible},
                            dates, regime, "REGIME_CALENDAR"
                        )

                        perm = permutation_distribution(
                            rng, len(event_values), eligible_values, PERMUTATIONS
                        )
                        perm_p = empirical_two_sided_p(event_mean, perm)

                        shift = frozen_shift_placebo(
                            mask,
                            {i: outcomes[i][outcome_name] for i in eligible},
                            h,
                        )

                        key = f"{target}|{h}|{hypothesis}|{outcome_name}"
                        pvalues.append((key, perm_p))

                        full_year = {}
                        by_year = defaultdict(list)
                        for i in event_indices:
                            by_year[dates[i].year].append(outcomes[i][outcome_name])
                        for year, vals in by_year.items():
                            if len(vals) >= MIN_N:
                                full_year[str(year)] = summarize(vals)

                        record = {
                            "key": key,
                            "target": target,
                            "price_symbol": symbol,
                            "horizon_sessions": h,
                            "hypothesis": hypothesis,
                            "family": meta["family"],
                            "outcome": outcome_name,
                            "event": summarize(event_values),
                            "controls": {
                                "unconditional_complement_mean": complement_mean,
                                "incremental_vs_complement": None if complement_mean is None else event_mean - complement_mean,
                                "regime_matched_mean": mean(regime_base) if regime_base else None,
                                "incremental_vs_regime": None if not regime_base else event_mean - mean(regime_base),
                                "calendar_month_matched_mean": mean(cal_base) if cal_base else None,
                                "incremental_vs_calendar_month": None if not cal_base else event_mean - mean(cal_base),
                                "regime_calendar_matched_mean": mean(regime_cal_base) if regime_cal_base else None,
                                "incremental_vs_regime_calendar": None if not regime_cal_base else event_mean - mean(regime_cal_base),
                                "frozen_shift_placebo_mean": mean(shift) if shift else None,
                                "incremental_vs_frozen_shift_placebo": None if not shift else event_mean - mean(shift),
                            },
                            "permutation": {
                                "iterations": PERMUTATIONS,
                                "empirical_p": perm_p,
                                "null_mean": mean(perm) if perm else None,
                            },
                            "full_year": full_year,
                        }
                        tests.append(record)

    q = bh(pvalues)
    supported = 0

    for r in tests:
        r["bh_q"] = q.get(r["key"], 1.0)
        ev = r["event"]
        ctl = r["controls"]
        year_means = [x["mean"] for x in r["full_year"].values()]

        # Outcome-specific minimum incremental magnitude.
        if r["outcome"] == "FORWARD_RETURN":
            min_effect = 0.0010
        elif r["outcome"] in ("ABSOLUTE_RETURN", "MAX_ADVERSE_EXCURSION", "MAX_FAVORABLE_EXCURSION"):
            min_effect = 0.0010
        elif r["outcome"] == "REALIZED_VOLATILITY":
            min_effect = 0.0050
        else:  # turning-point probability
            min_effect = 0.02

        increments = [
            ctl.get("incremental_vs_complement"),
            ctl.get("incremental_vs_regime"),
            ctl.get("incremental_vs_calendar_month"),
            ctl.get("incremental_vs_regime_calendar"),
            ctl.get("incremental_vs_frozen_shift_placebo"),
        ]
        available_inc = [x for x in increments if x is not None]
        consistent_controls = (
            len(available_inc) >= 3
            and sum(1 for x in available_inc if x * mean(available_inc) > 0) >= 3
        )

        year_consistency = (
            len(year_means) >= 2
            and sum(1 for x in year_means if x * ev["mean"] > 0) >= 2
        )

        gate = {
            "sample_size": ev["n"] >= MIN_N,
            "permutation_bh_q_le_0_05": r["bh_q"] <= 0.05,
            "incremental_effect_abs_ge_threshold": (
                abs(ctl.get("incremental_vs_complement") or 0) >= min_effect
            ),
            "control_direction_consistency": consistent_controls,
            "full_year_consistency": year_consistency,
            "independent_ephemeris_parity": r["family"] == "LUNAR",
        }
        r["research_gate"] = gate
        r["status"] = "RESEARCH_SUPPORTED" if all(gate.values()) else "UNSUPPORTED"
        supported += r["status"] == "RESEARCH_SUPPORTED"

    out = {
        "version": "M77.14.1-INCREMENTAL-BASELINE-PERMUTATION-OUTCOME-HARDENING-1.0",
        "status": "READY",
        "governance": {
            "research_only": True,
            "database_read_only": True,
            "database_writes": False,
            "production_authority_effect": False,
            "automatic_promotion": False,
            "hypotheses_frozen_from_m77_14": True,
            "neighboring_window_search": False,
        },
        "targets": resolved,
        "horizons": HORIZONS,
        "frozen_outcomes": FROZEN_OUTCOMES,
        "permutations_per_test": PERMUTATIONS,
        "multiple_testing": "BENJAMINI_HOCHBERG_ON_EMPIRICAL_PERMUTATION_P",
        "result_count": len(tests),
        "research_supported_count": supported,
        "traditional_astrology_disposition": "QUARANTINED_PENDING_INDEPENDENT_EPHEMERIS_PARITY",
        "results": tests,
        "next_step": (
            "REVIEW_INCREMENTAL_BASELINE_EVIDENCE; "
            "IF_LUNAR_SURVIVES_BUILD_PROSPECTIVE_SHADOW; "
            "TRADITIONAL_REQUIRES_EPHEMERIS_PARITY_FIRST"
        ),
        "production_authority_effect": False,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n")

    print(json.dumps({
        "version": out["version"],
        "status": out["status"],
        "targets": out["targets"],
        "result_count": out["result_count"],
        "research_supported_count": out["research_supported_count"],
        "permutations_per_test": out["permutations_per_test"],
        "traditional_astrology_disposition": out["traditional_astrology_disposition"],
        "next_step": out["next_step"],
        "production_authority_effect": False,
    }, indent=2))

if __name__ == "__main__":
    main()
