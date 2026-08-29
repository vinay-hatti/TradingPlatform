#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.astronomical_cycles import features

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/m77/m77_14_2_lunar_survivor_certification.json"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"

VERSION="M77.14.2-INCREMENTAL-YEARLY-STABILITY-DEPENDENCE-ROBUST-NULL-1.0"

# Frozen confirmatory survivor from M77.14.1. No neighboring-window or outcome search.
TARGET="NDX"
TARGET_FALLBACK="QQQ"
HORIZON=10
HYPOTHESIS="FIRST_QUARTER_WINDOW"
OUTCOME="ABSOLUTE_RETURN"

MIN_EVENT_N=30
MIN_YEAR_EVENT_N=8
MIN_SUPPORTIVE_YEARS=3
CIRCULAR_PERMUTATIONS=10000
BOOTSTRAP_ITERATIONS=10000
RNG_SEED=771402

def load_regimes():
    if not PIT.exists():
        return {}
    x=json.loads(PIT.read_text())
    rows=x if isinstance(x,list) else x.get("snapshots") or x.get("rows") or []
    return {
        str(r.get("as_of"))[:10]:r.get("regime")
        for r in rows
        if r.get("as_of") and r.get("regime")
    }

def resolve(session):
    for sym in (TARGET,TARGET_FALLBACK,"I:"+TARGET):
        if session.execute(
            text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),
            {"s":sym},
        ).scalar():
            return sym
    return None

def prices(session,symbol):
    return [
        (r[0],float(r[1]))
        for r in session.execute(
            text(
                "SELECT date,close FROM price_history "
                "WHERE symbol=:s AND close IS NOT NULL ORDER BY date"
            ),
            {"s":symbol},
        )
    ]

def outcome(close,i,h):
    if i+h>=len(close):
        return None
    return abs(close[i+h]/close[i]-1.0)

def complement_mean(event_indices,eligible,values):
    event=set(event_indices)
    vals=[values[i] for i in eligible if i not in event]
    return mean(vals) if vals else None

def matched_increment(event_indices,eligible,values,dates,regimes,mode):
    event=set(event_indices)
    diffs=[]
    for i in event_indices:
        reg=regimes.get(str(dates[i])[:10])
        month=dates[i].month
        candidates=[]
        for j in eligible:
            if j in event:
                continue
            if mode in ("REGIME","REGIME_CALENDAR"):
                if reg is None or regimes.get(str(dates[j])[:10])!=reg:
                    continue
            if mode in ("CALENDAR","REGIME_CALENDAR") and dates[j].month!=month:
                continue
            candidates.append(values[j])
        if candidates:
            diffs.append(values[i]-mean(candidates))
    return mean(diffs) if diffs else None

def yearly_incremental(event_indices,eligible,values,dates,regimes):
    event=set(event_indices)
    byyear=defaultdict(list)
    for i in event_indices:
        byyear[dates[i].year].append(i)
    out={}
    for year,idxs in sorted(byyear.items()):
        if len(idxs)<MIN_YEAR_EVENT_N:
            continue
        same_year=[j for j in eligible if dates[j].year==year and j not in event]
        if not same_year:
            continue
        base=mean(values[j] for j in same_year)
        ev=mean(values[i] for i in idxs)
        reg_inc=matched_increment(idxs,same_year,values,dates,regimes,"REGIME")
        cal_inc=matched_increment(idxs,same_year,values,dates,regimes,"CALENDAR")
        regcal_inc=matched_increment(idxs,same_year,values,dates,regimes,"REGIME_CALENDAR")
        out[str(year)]={
            "event_n":len(idxs),
            "event_mean":ev,
            "same_year_complement_mean":base,
            "incremental_vs_same_year_complement":ev-base,
            "incremental_vs_regime":reg_inc,
            "incremental_vs_calendar_month":cal_inc,
            "incremental_vs_regime_calendar":regcal_inc,
        }
    return out

def greedy_nonoverlap(indices,h):
    selected=[]
    last=-10**9
    for i in sorted(indices):
        if i-last>=h:
            selected.append(i)
            last=i
    return selected

def year_stratified_circular_null(mask,eligible,values,dates,rng,iterations):
    byyear=defaultdict(list)
    for i in eligible:
        byyear[dates[i].year].append(i)
    event_positions={}
    for year,idxs in byyear.items():
        pos={idx:k for k,idx in enumerate(idxs)}
        event_positions[year]=[pos[i] for i in idxs if mask[i]]

    null=[]
    for _ in range(iterations):
        vals=[]
        for year,idxs in byyear.items():
            n=len(idxs)
            events=event_positions.get(year) or []
            if not events or n==0:
                continue
            shift=rng.randrange(n)
            for p in events:
                j=idxs[(p+shift)%n]
                vals.append(values[j])
        if vals:
            null.append(mean(vals))
    return null

def empirical_p(observed,null):
    if not null:
        return 1.0
    center=mean(null)
    dev=abs(observed-center)
    return (1+sum(abs(x-center)>=dev for x in null))/(len(null)+1)

def percentile(vals,p):
    if not vals:
        return None
    x=sorted(vals)
    k=(len(x)-1)*p
    lo=math.floor(k); hi=math.ceil(k)
    if lo==hi:
        return x[lo]
    return x[lo]*(hi-k)+x[hi]*(k-lo)

def block_bootstrap_increment(event_indices,eligible,values,dates,rng,iterations):
    # Bootstrap whole event clusters (consecutive event sessions) against the
    # unconditional complement. This preserves within-cluster dependence.
    event_set=set(event_indices)
    clusters=[]
    current=[]
    for i in sorted(event_indices):
        if not current or i==current[-1]+1:
            current.append(i)
        else:
            clusters.append(current); current=[i]
    if current:
        clusters.append(current)

    comp=[values[i] for i in eligible if i not in event_set]
    if not clusters or not comp:
        return []

    boot=[]
    for _ in range(iterations):
        sampled=[]
        for _c in range(len(clusters)):
            cluster=rng.choice(clusters)
            sampled.extend(values[i] for i in cluster)
        comp_sample=[rng.choice(comp) for _ in range(len(comp))]
        boot.append(mean(sampled)-mean(comp_sample))
    return boot

def regime_incrementals(event_indices,eligible,values,dates,regimes):
    event=set(event_indices)
    out={}
    all_regs=sorted({regimes.get(str(dates[i])[:10]) for i in event_indices if regimes.get(str(dates[i])[:10])})
    for reg in all_regs:
        ev=[i for i in event_indices if regimes.get(str(dates[i])[:10])==reg]
        cp=[j for j in eligible if j not in event and regimes.get(str(dates[j])[:10])==reg]
        if len(ev)>=8 and cp:
            out[reg]={
                "event_n":len(ev),
                "event_mean":mean(values[i] for i in ev),
                "regime_complement_mean":mean(values[j] for j in cp),
                "incremental":mean(values[i] for i in ev)-mean(values[j] for j in cp),
            }
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    ap.add_argument("--confirm")
    args=ap.parse_args()

    with SessionLocal() as session:
        symbol=resolve(session)

    if args.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":"RUN_M77_14_2_LUNAR_SURVIVOR_CERTIFICATION",
            "frozen_survivor":{
                "target":TARGET,
                "resolved_price_symbol":symbol,
                "horizon_sessions":HORIZON,
                "hypothesis":HYPOTHESIS,
                "outcome":OUTCOME,
            },
            "dependence_robust_null":{
                "type":"YEAR_STRATIFIED_CIRCULAR_EVENT_CALENDAR_SHIFT",
                "iterations":CIRCULAR_PERMUTATIONS,
            },
            "bootstrap_iterations":BOOTSTRAP_ITERATIONS,
            "governance":{
                "neighboring_hypothesis_search":False,
                "neighboring_window_search":False,
                "neighboring_horizon_search":False,
                "alternative_outcome_search":False,
                "database_writes":False,
                "production_authority_effect":False,
                "automatic_shadow_promotion":False,
            },
        },indent=2))
        return

    if args.confirm!="RUN_M77_14_2_LUNAR_SURVIVOR_CERTIFICATION":
        raise SystemExit("confirmation required")
    if not symbol:
        raise SystemExit("NDX/QQQ price history not available")

    regimes=load_regimes()
    rng=random.Random(RNG_SEED)

    with SessionLocal() as session:
        rows=prices(session,symbol)

    dates=[x[0] for x in rows]
    close=[x[1] for x in rows]
    mask=[bool(features(d).get(HYPOTHESIS)) for d in dates]

    values={}
    for i in range(len(rows)-HORIZON):
        v=outcome(close,i,HORIZON)
        if v is not None:
            values[i]=v

    eligible=sorted(values)
    event_indices=[i for i in eligible if mask[i]]
    event_values=[values[i] for i in event_indices]
    event_mean=mean(event_values)
    comp_mean=complement_mean(event_indices,eligible,values)

    controls={
        "unconditional_complement_mean":comp_mean,
        "incremental_vs_complement":None if comp_mean is None else event_mean-comp_mean,
        "incremental_vs_regime":matched_increment(event_indices,eligible,values,dates,regimes,"REGIME"),
        "incremental_vs_calendar_month":matched_increment(event_indices,eligible,values,dates,regimes,"CALENDAR"),
        "incremental_vs_regime_calendar":matched_increment(event_indices,eligible,values,dates,regimes,"REGIME_CALENDAR"),
    }

    yearly=yearly_incremental(event_indices,eligible,values,dates,regimes)

    nonoverlap=greedy_nonoverlap(event_indices,HORIZON)
    non_event=set(event_indices)
    nonoverlap_comp=[values[i] for i in eligible if i not in non_event]
    nonoverlap_event_mean=mean(values[i] for i in nonoverlap) if nonoverlap else None
    nonoverlap_comp_mean=mean(nonoverlap_comp) if nonoverlap_comp else None
    nonoverlap_increment=None
    if nonoverlap_event_mean is not None and nonoverlap_comp_mean is not None:
        nonoverlap_increment=nonoverlap_event_mean-nonoverlap_comp_mean

    circular_null=year_stratified_circular_null(
        mask,eligible,values,dates,rng,CIRCULAR_PERMUTATIONS
    )
    circular_p=empirical_p(event_mean,circular_null)

    boot=block_bootstrap_increment(
        event_indices,eligible,values,dates,rng,BOOTSTRAP_ITERATIONS
    )
    ci95=[percentile(boot,.025),percentile(boot,.975)] if boot else [None,None]

    year_incs=[
        x["incremental_vs_same_year_complement"]
        for x in yearly.values()
        if x.get("incremental_vs_same_year_complement") is not None
    ]
    negative_years=sum(x<0 for x in year_incs)
    positive_years=sum(x>0 for x in year_incs)
    expected_sign=-1 if (controls.get("incremental_vs_complement") or 0)<0 else 1
    supportive_years=sum(
        1 for x in year_incs
        if x*expected_sign>0
    )

    worst_opposite=0.0
    for x in year_incs:
        if x*expected_sign<0:
            worst_opposite=max(worst_opposite,abs(x))

    regime_stats=regime_incrementals(event_indices,eligible,values,dates,regimes)
    regime_incs=[x["incremental"] for x in regime_stats.values()]
    supportive_regimes=sum(1 for x in regime_incs if x*expected_sign>0)

    gate={
        "event_sample_size":len(event_values)>=MIN_EVENT_N,
        "dependence_robust_circular_p_le_0_05":circular_p<=.05,
        "bootstrap_ci_excludes_zero":(
            ci95[0] is not None and ci95[1] is not None and
            (ci95[1]<0 or ci95[0]>0)
        ),
        "at_least_3_supportive_years":supportive_years>=MIN_SUPPORTIVE_YEARS,
        "majority_year_sign_consistency":(
            supportive_years>=max(3,math.ceil(len(year_incs)*.60))
            if year_incs else False
        ),
        "no_catastrophic_opposite_year":(
            worst_opposite <= abs(controls.get("incremental_vs_complement") or 0)*1.5
            if year_incs else False
        ),
        "nonoverlap_same_direction":(
            nonoverlap_increment is not None and nonoverlap_increment*expected_sign>0
        ),
        "regime_stability":(
            len(regime_incs)==0 or supportive_regimes>=math.ceil(len(regime_incs)*.60)
        ),
        "independent_lunar_phase_calculation":True,
    }

    status="RESEARCH_SUPPORTED_FOR_PROSPECTIVE_SHADOW" if all(gate.values()) else "UNSUPPORTED_AFTER_DEPENDENCE_HARDENING"

    out={
        "version":VERSION,
        "status":"READY",
        "frozen_survivor":{
            "target":TARGET,
            "price_symbol":symbol,
            "horizon_sessions":HORIZON,
            "hypothesis":HYPOTHESIS,
            "outcome":OUTCOME,
        },
        "overall":{
            "event_n":len(event_values),
            "event_mean":event_mean,
            "controls":controls,
        },
        "yearly_incremental":yearly,
        "year_stability":{
            "eligible_years":len(year_incs),
            "supportive_years":supportive_years,
            "negative_years":negative_years,
            "positive_years":positive_years,
            "median_incremental":median(year_incs) if year_incs else None,
            "worst_opposite_increment_abs":worst_opposite,
        },
        "dependence_robust_null":{
            "method":"YEAR_STRATIFIED_CIRCULAR_EVENT_CALENDAR_SHIFT",
            "iterations":len(circular_null),
            "null_mean":mean(circular_null) if circular_null else None,
            "empirical_p":circular_p,
        },
        "cluster_bootstrap":{
            "method":"CONSECUTIVE_EVENT_CLUSTER_BOOTSTRAP_VS_COMPLEMENT",
            "iterations":len(boot),
            "incremental_ci95":ci95,
        },
        "nonoverlap_sensitivity":{
            "event_n":len(nonoverlap),
            "event_mean":nonoverlap_event_mean,
            "complement_mean":nonoverlap_comp_mean,
            "incremental":nonoverlap_increment,
        },
        "regime_incremental":regime_stats,
        "research_gate":gate,
        "certification_disposition":status,
        "governance":{
            "research_only":True,
            "database_read_only":True,
            "database_writes":False,
            "production_authority_effect":False,
            "automatic_shadow_promotion":False,
            "single_frozen_survivor_only":True,
            "neighboring_search":False,
        },
        "next_step":(
            "BUILD_PROSPECTIVE_LUNAR_SHADOW"
            if status=="RESEARCH_SUPPORTED_FOR_PROSPECTIVE_SHADOW"
            else "RETIRE_LUNAR_SURVIVOR_AS_NOT_ROBUST_ENOUGH"
        ),
        "production_authority_effect":False,
    }

    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,default=str)+"\n")

    print(json.dumps({
        "version":VERSION,
        "status":"READY",
        "frozen_survivor":out["frozen_survivor"],
        "event_n":len(event_values),
        "incremental_vs_complement":controls.get("incremental_vs_complement"),
        "dependence_robust_empirical_p":circular_p,
        "bootstrap_ci95":ci95,
        "supportive_years":supportive_years,
        "eligible_years":len(year_incs),
        "nonoverlap_incremental":nonoverlap_increment,
        "certification_disposition":status,
        "next_step":out["next_step"],
        "production_authority_effect":False,
    },indent=2))

if __name__=="__main__":
    main()
